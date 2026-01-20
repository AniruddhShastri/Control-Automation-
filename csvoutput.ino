#include <Wire.h>
#include <LittleFS.h>

#define ADS1115_ADDRESS 0x48
#define RELAY_PIN D5

const float TEMP_LOW_THRESHOLD = 32.0;   // Turn heater ON below this
const float TEMP_HIGH_THRESHOLD = 37.0; 
bool heaterState = false;  

// VARIABLE DECLARATIONS
//===================================================

// Shunt resistor and transformer parameters
const float Rshunt = 0.050;        
const float n_trafo = 1000.0;      

// RMS calculation and averaging
double quadratic_sum_rms = 0.0;
const int sampleDuration = 20;     
int quadratic_sum_counter = 0;

double accumulated_current = 0.0;
const int sampleAverage = 50;      // Reduced: ~1 second (was 250 = 5s)
int accumulated_counter = 0;

unsigned long time_ant = 0;
unsigned long difTime = 0;
unsigned long act_time = 0;

byte writeBuf[3];

double v_bias = 1.64;  

// LM35 Temperature sensor variables
#define LM35_PIN A1             
const float LM35_VREF = 3.3;       
const float LM35_SCALE = 100.0;    

// Timing: 5 READINGS PER SECOND (200ms interval)
unsigned long rms_sample_time_us = 0;
unsigned long display_time = 0;
const unsigned long display_interval = 200;  // *** 200ms = 5 readings per second ***

// CSV Logging variables
const char* csvFileName = "/sensor_data.csv";
bool csvLoggingEnabled = true;
bool csvHeaderWritten = false;

//=================================================================================================================================
// Helper functions (unchanged)
void config_i2c() {
  Wire.begin();
  writeBuf[0] = 1;
  writeBuf[1] = 0b11010010;
  writeBuf[2] = 0b11100101;
  Wire.beginTransmission(ADS1115_ADDRESS);
  Wire.write(writeBuf[0]);
  Wire.write(writeBuf[1]);
  Wire.write(writeBuf[2]);
  Wire.endTransmission();
  delay(500);
}

float read_voltage() {
  Wire.beginTransmission(ADS1115_ADDRESS);
  Wire.write(0x00);
  Wire.endTransmission();
  Wire.requestFrom(ADS1115_ADDRESS, 2);
  int16_t result = Wire.read() << 8 | Wire.read();
  float voltage = result * 4.096 / 32768.0;
  return voltage;
}

float read_temperature() {
  int adc_value = analogRead(LM35_PIN);
  float voltage = (adc_value * LM35_VREF) / 4095.0;
  float temperature = voltage * LM35_SCALE;
  return temperature;
}

void controlHeater(float temperature) {  
  // Hysteresis control: prevents rapid switching near thresholds
  if (temperature < TEMP_LOW_THRESHOLD) {   // Below 32°C: Turn heater ON
    if (!heaterState) {
      digitalWrite(RELAY_PIN, HIGH);
      heaterState = true;
      Serial.println(">>> Heater TURNED ON (Temp < 32°C)");
    }
  } 
  else if (temperature > TEMP_HIGH_THRESHOLD) {
    // Above 37°C: Turn heater OFF
    if (heaterState) {
      digitalWrite(RELAY_PIN, LOW);
      heaterState = false;
      Serial.println(">>> Heater TURNED OFF (Temp > 37°C)");
    }
  }
}

// Write CSV header to file
void writeCSVHeader() {
  if (!csvLoggingEnabled) return;
  
  File file = LittleFS.open(csvFileName, "w");
  if (file) {
    file.println("Timestamp(ms),Time(s),Current(A),Temperature(C),Heater_State");
    file.close();
    csvHeaderWritten = true;
    Serial.println("✓ CSV header written");
  } else {
    Serial.println("✗ Failed to write CSV header");
  }
}

// Append data to CSV file
void appendToCSV(unsigned long timestamp_ms, unsigned long time_s, double current, float temperature, bool heater) {
  if (!csvLoggingEnabled) return;
  
  File file = LittleFS.open(csvFileName, "a");
  if (file) {
    file.print(timestamp_ms);
    file.print(",");
    file.print(time_s);
    file.print(",");
    file.print(current, 5);
    file.print(",");
    file.print(temperature, 2);
    file.print(",");
    file.println(heater ? "ON" : "OFF");
    file.close();
  } else {
    Serial.println("✗ Failed to append to CSV");
  }
}

// Dump CSV file contents to Serial Monitor
void dumpCSVToSerial() {
  if (!csvLoggingEnabled) {
    Serial.println("✗ CSV logging is disabled");
    return;
  }
  
  File file = LittleFS.open(csvFileName, "r");
  if (!file) {
    Serial.println("✗ Failed to open CSV file for reading");
    return;
  }
  
  size_t fileSize = file.size();
  int lineCount = 0;
  
  // Clear markers for Python script to detect
  Serial.println("\n[CSV_START]");
  Serial.print("File: ");
  Serial.println(csvFileName);
  Serial.print("Size: ");
  Serial.print(fileSize);
  Serial.println(" bytes");
  Serial.flush();  // Ensure header is sent
  
  // Output CSV content line by line with proper flushing
  while (file.available()) {
    String line = file.readStringUntil('\n');
    line.trim();  // Remove any trailing whitespace
    
    if (line.length() > 0) {  // Only send non-empty lines
      // Validate line has expected format (5 comma-separated values)
      int commaCount = 0;
      for (int i = 0; i < line.length(); i++) {
        if (line.charAt(i) == ',') commaCount++;
      }
      
      // Only send if line has 4 commas (5 columns)
      if (commaCount == 4) {
        Serial.print(line);  // Use print instead of println for more control
        Serial.print('\n');   // Explicit newline
        Serial.flush();        // Flush immediately to ensure complete line is sent
        lineCount++;
        
        // Additional flush every 25 lines to prevent buffer overflow
        if (lineCount % 25 == 0) {
          delay(20);  // Slightly longer delay to ensure transmission
        }
      } else {
        // Skip malformed lines (log for debugging)
        Serial.print("# SKIPPED MALFORMED LINE: ");
        Serial.print(commaCount);
        Serial.print(" commas (expected 4): ");
        Serial.println(line.substring(0, 40));  // First 40 chars only
      }
    }
  }
  
  // Final flush to ensure all data is sent
  Serial.flush();
  delay(50);  // Wait a bit before sending end marker
  
  Serial.println("[CSV_END]");
  Serial.flush();
  delay(50);
  
  Serial.print("✓ CSV data sent. Total lines: ");
  Serial.print(lineCount);
  Serial.println(". Use Python script to auto-save to Desktop.\n");
  Serial.flush();
  
  file.close();
}

// Get CSV file size
size_t getCSVFileSize() {
  File file = LittleFS.open(csvFileName, "r");
  if (!file) return 0;
  size_t size = file.size();
  file.close();
  return size;
}

// Check for Serial commands
void checkSerialCommands() {
  if (Serial.available()) {
    String command = Serial.readStringUntil('\n');
    command.trim();
    command.toLowerCase();
    
    if (command == "dump" || command == "d") {
      dumpCSVToSerial();
    } else if (command == "info" || command == "i") {
      Serial.println("\n=== CSV FILE INFO ===");
      Serial.print("File: ");
      Serial.println(csvFileName);
      Serial.print("Size: ");
      Serial.print(getCSVFileSize());
      Serial.println(" bytes");
      Serial.print("Status: ");
      Serial.println(csvLoggingEnabled ? "✓ Active" : "✗ Disabled");
      Serial.println("====================\n");
    } else if (command == "help" || command == "h") {
      Serial.println("\n=== AVAILABLE COMMANDS ===");
      Serial.println("dump  or  d  - Dump CSV file contents to Serial");
      Serial.println("info  or  i  - Show CSV file information");
      Serial.println("help  or  h  - Show this help message");
      Serial.println("==========================\n");
    }
  }
}


void setup() {
  Serial.begin(115200);
  config_i2c();

  pinMode(RELAY_PIN, OUTPUT);
  digitalWrite(RELAY_PIN, HIGH);  // Start OFF
  heaterState = false;

  delay(100);
  Serial.println("=== Current + Temperature + Heater Control ===");
  Serial.println("Heater ON: Temp < 32°C | Heater OFF: Temp > 37°C");
  
  // Initialize LittleFS for CSV logging
  if (!LittleFS.begin(true)) {
    Serial.println("✗ LittleFS mount failed! CSV logging disabled.");
    csvLoggingEnabled = false;
  } else {
    Serial.println("✓ LittleFS mounted successfully");
    Serial.println("📁 CSV file path: /sensor_data.csv (on ESP32 filesystem)");
    Serial.println("📊 Logging interval: 5 readings per second (200ms)");
    writeCSVHeader();
  }
  
  Serial.println("Time | Current (A) | Temp (°C) | Heater");
  Serial.println("-----------------------------------------------");
  Serial.println("📊 Data capture: 5 readings per second");
  
  Serial.println("\n=== SERIAL COMMANDS ===");
  Serial.println("Type 'dump' or 'd' to output CSV file to Serial");
  Serial.println("Type 'info' or 'i' to see file information");
  Serial.println("Type 'help' or 'h' for all commands");
  Serial.println("======================\n");
  
  display_time = millis();
}

void loop() {
  act_time = micros();
  difTime = act_time - time_ant;

  if (difTime >= 1000) {
    time_ant = act_time;
    double Vinst = read_voltage() - v_bias;
    double Inst = Vinst * 20;
    quadratic_sum_rms += Inst * Inst * (difTime / 1000000.0);
    rms_sample_time_us += difTime;
  }

  if (rms_sample_time_us >= 20000) {
    double Irms = sqrt(quadratic_sum_rms / (rms_sample_time_us / 1000000.0));
    if (Irms < 0.1) Irms = 0.0;
    accumulated_current += Irms;
    accumulated_counter++;
    quadratic_sum_rms = 0.0;
    rms_sample_time_us = 0;
  }

  // *** 5 READINGS PER SECOND (200ms interval) ***
  unsigned long now = millis();
  if (now - display_time >= display_interval) {
    display_time = now;
    
    double Iavg = 0.0;
    if (accumulated_counter > 0) {
      Iavg = accumulated_current / accumulated_counter;
      accumulated_current = 0.0;
      accumulated_counter = 0;
    }
    
    float temperature = read_temperature();
    
    // Control heater based on temperature with hysteresis
    controlHeater(temperature);

    // Print to Serial Monitor
    unsigned long currentTime_s = millis()/1000;
    Serial.print(currentTime_s);
    Serial.print("s | ");
    Serial.print(Iavg, 5);
    Serial.print(" A | ");
    Serial.print(temperature, 2);
    Serial.print(" °C | ");
    Serial.println(heaterState ? "ON" : "OFF");
    
    // Log to CSV file (5 times per second)
    appendToCSV(millis(), currentTime_s, Iavg, temperature, heaterState);
  }
  
  // Check for Serial commands
  checkSerialCommands();
}