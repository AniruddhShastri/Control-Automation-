import serial
import serial.tools.list_ports
import os
from datetime import datetime
import sys
import time
import argparse

def find_esp32_port():
    """Try to find ESP32 port automatically"""
    ports = serial.tools.list_ports.comports()
    esp32_ports = []
    
    for port in ports:
        # Common ESP32 identifiers
        desc_upper = port.description.upper()
        if any(keyword in desc_upper for keyword in ['ESP32', 'CH340', 'CP210', 'FTDI', 'USB', 'SERIAL']):
            esp32_ports.append(port.device)
    
    return esp32_ports

def get_desktop_path():
    """Get Desktop path for current user"""
    if sys.platform == "darwin":  # macOS
        return os.path.join(os.path.expanduser("~"), "Desktop")
    elif sys.platform == "win32":  # Windows
        return os.path.join(os.path.expanduser("~"), "Desktop")
    else:  # Linux
        return os.path.join(os.path.expanduser("~"), "Desktop")

def fix_csv_file(filepath):
    """Fix an existing CSV file with alignment issues"""
    print("=" * 70)
    print("CSV File Fixer")
    print("=" * 70)
    print(f"Fixing: {filepath}\n")
    
    if not os.path.exists(filepath):
        print(f"❌ File not found: {filepath}")
        return
    
    # Read original file
    fixed_lines = []
    skipped_lines = 0
    fixed_count = 0
    
    with open(filepath, 'r', encoding='utf-8') as f:
        for line_num, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            
            columns = [col.strip() for col in line.split(',') if col.strip()]
            
            if len(columns) == 5:
                fixed_lines.append(','.join(columns))
            else:
                fixed = fix_csv_line(line, columns)
                if fixed:
                    fixed_lines.append(fixed)
                    fixed_count += 1
                else:
                    skipped_lines += 1
                    if skipped_lines <= 10:
                        print(f"⚠ Line {line_num}: Skipped (can't fix): {line[:60]}")
    
    # Write fixed file
    backup_path = filepath + '.backup'
    os.rename(filepath, backup_path)
    print(f"✓ Original file backed up to: {backup_path}")
    
    with open(filepath, 'w', newline='', encoding='utf-8') as f:
        for line in fixed_lines:
            f.write(line + '\n')
    
    print(f"\n✅ Fixed file saved!")
    print(f"   Original: {backup_path}")
    print(f"   Fixed: {filepath}")
    print(f"   Total lines: {len(fixed_lines)}")
    print(f"   Fixed: {fixed_count}")
    print(f"   Skipped: {skipped_lines}")
    print("=" * 70)

def fix_csv_line(line, columns):
    """
    Fix common CSV line issues:
    - Missing timestamp (add placeholder or estimate)
    - Column misalignment
    - Missing values
    """
    # Expected format: Timestamp(ms),Time(s),Current(A),Temperature(C),Heater_State
    # Expected: 5 columns
    
    # Remove empty columns
    columns = [col.strip() for col in columns if col.strip()]
    
    if len(columns) == 5:
        # Perfect line, return as is
        return ','.join(columns)
    elif len(columns) == 4:
        # Missing one column - likely missing timestamp
        # Check if first column looks like a timestamp (large number)
        try:
            first_val = int(columns[0])
            if first_val < 1000:  # Too small to be timestamp, probably missing
                # Insert placeholder timestamp (will be estimated later)
                return f"0,{','.join(columns)}"
            else:
                # First is timestamp, missing last column (heater state)
                return f"{','.join(columns)},UNKNOWN"
        except ValueError:
            # First column is not a number, missing timestamp
            return f"0,{','.join(columns)}"
    elif len(columns) == 3:
        # Missing timestamp and one other column
        # Try to identify what's missing by data type
        try:
            # Check if first is time_s (small number < 10000)
            first_val = float(columns[0])
            if first_val < 10000:
                # Missing timestamp, has time_s, current, temp - missing heater
                return f"0,{','.join(columns)},UNKNOWN"
            else:
                # First might be timestamp, missing time_s and heater
                return f"{columns[0]},0,{columns[1]},{columns[2]},UNKNOWN"
        except ValueError:
            return f"0,0,{','.join(columns)},UNKNOWN"
    elif len(columns) > 5:
        # Too many columns - might have extra commas in data
        # Try to merge last columns if they look like they should be together
        if len(columns) == 6:
            # Might be: timestamp, time_s, current, temp_part1, temp_part2, heater
            # Or: timestamp, time_s, current, temp, heater_part1, heater_part2
            try:
                # Try to combine columns 3 and 4 if column 4 is a small number
                float(columns[3])
                float(columns[4])
                # Both are numbers, probably temp got split
                return f"{columns[0]},{columns[1]},{columns[2]},{columns[3]}.{columns[4]},{columns[5]}"
            except ValueError:
                # Not numbers, return first 5
                return ','.join(columns[:5])
        else:
            # Too many, just take first 5
            return ','.join(columns[:5])
    else:
        # Too few columns, can't fix reliably
        return None

def main():
    # Parse command line arguments
    parser = argparse.ArgumentParser(description='ESP32 CSV Auto-Capture Tool')
    parser.add_argument('-p', '--port', type=str, help='COM port name (e.g., COM11)')
    parser.add_argument('-f', '--fix', type=str, help='Fix an existing CSV file (provide path)')
    args = parser.parse_args()
    
    # If fix mode, process the file and exit
    if args.fix:
        fix_csv_file(args.fix)
        return
    
    print("=" * 70)
    print("ESP32 CSV Auto-Capture Tool")
    print("=" * 70)
    
    # Find available ports
    ports = list(serial.tools.list_ports.comports())
    if not ports:
        print("❌ No serial ports found!")
        input("Press Enter to exit...")
        return
    
    print("\nAvailable ports:")
    for i, port in enumerate(ports):
        # Highlight potential ESP32 ports
        is_esp32 = any(keyword in port.description.upper() for keyword in ['ESP32', 'CH340', 'CP210', 'FTDI', 'USB', 'SERIAL'])
        marker = " ⭐" if is_esp32 else ""
        print(f"  {i+1}. {port.device} - {port.description}{marker}")
    
    # If port specified via command line, use it
    if args.port:
        port_name = args.port.upper()
        if not port_name.startswith("COM"):
            port_name = "COM" + port_name
        # Verify it exists
        if not any(p.device.upper() == port_name for p in ports):
            print(f"\n❌ Port {port_name} not found in available ports!")
            print("Available ports:")
            for p in ports:
                print(f"  - {p.device}")
            input("\nPress Enter to exit...")
            return
        print(f"\n✓ Using command-line specified port: {port_name}")
    else:
        # Auto-detect ESP32
        esp32_ports = find_esp32_port()
        if esp32_ports:
            print(f"\n⚠ Auto-detected potential ESP32 port: {esp32_ports[0]}")
            print("   But please verify this is correct!")
        
        # Ask user to select port
        print(f"\n📌 Please select your ESP32 port:")
        print("   (Look for the port that matches your ESP32 connection)")
        print("   Tip: You can also run: python esp32_csv_capture.py -p COM11")
        
        try:
            choice = input(f"\nEnter port number (1-{len(ports)}) or COM port name (e.g., COM11): ").strip().upper()
            
            if choice == "":
                print("❌ No selection made")
                input("Press Enter to exit...")
                return
            
            # Check if user entered a COM port name directly (e.g., "COM11")
            if choice.startswith("COM"):
                port_name = choice
                # Verify it exists
                if not any(p.device.upper() == choice for p in ports):
                    print(f"❌ Port {choice} not found in available ports!")
                    print("Available ports:")
                    for p in ports:
                        print(f"  - {p.device}")
                    input("\nPress Enter to exit...")
                    return
                print(f"✓ Selected: {port_name}")
            else:
                # User entered a number
                try:
                    port_index = int(choice) - 1
                    if port_index < 0 or port_index >= len(ports):
                        print(f"❌ Invalid selection. Please choose 1-{len(ports)}")
                        input("Press Enter to exit...")
                        return
                    port_name = ports[port_index].device
                    print(f"✓ Selected: {port_name} - {ports[port_index].description}")
                except ValueError:
                    print("❌ Invalid input. Please enter a number or COM port name.")
                    input("Press Enter to exit...")
                    return
                    
        except KeyboardInterrupt:
            print("\n\n👋 Cancelled by user")
            return
    
    # Get baud rate
    baud_rate = 115200  # Default for ESP32
    
    # Get Desktop path
    desktop_path = get_desktop_path()
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    csv_filename = os.path.join(desktop_path, f"sensor_data_{timestamp}.csv")
    
    print(f"\n📁 Output file: {csv_filename}")
    print(f"📡 Connecting to {port_name} at {baud_rate} baud...")
    
    # Check if port is available before trying to connect
    print("\n⚠ IMPORTANT: Make sure Arduino IDE Serial Monitor is CLOSED!")
    print("   If it's open, close it completely and wait 2 seconds.\n")
    
    # Wait a moment for user to close other programs
    print("Waiting 3 seconds for you to close Arduino IDE Serial Monitor...")
    for i in range(3, 0, -1):
        print(f"   {i}...", end='\r')
        time.sleep(1)
    print("   Connecting now...\n")
    
    try:
        # Try to open the port with a timeout
        try:
            ser = serial.Serial(port_name, baud_rate, timeout=2)
        except serial.SerialException as port_error:
            print("=" * 70)
            print("❌ CANNOT ACCESS SERIAL PORT!")
            print("=" * 70)
            print(f"\nError: {port_error}")
            print("\n🔧 TROUBLESHOOTING STEPS:")
            print("\n1. CLOSE Arduino IDE Serial Monitor:")
            print("   - Go to Arduino IDE")
            print("   - Click the Serial Monitor icon (top right)")
            print("   - Close the Serial Monitor window completely")
            print("   - Wait 2-3 seconds")
            
            print("\n2. CLOSE any other programs using COM4:")
            print("   - Close any terminal/command prompt windows")
            print("   - Close any other serial monitor tools")
            print("   - Check Task Manager for any Arduino/Serial processes")
            
            print("\n3. UNPLUG and REPLUG your ESP32:")
            print("   - Unplug the USB cable")
            print("   - Wait 2 seconds")
            print("   - Plug it back in")
            print("   - Wait for Windows to recognize it")
            
            print("\n4. TRY RUNNING AS ADMINISTRATOR:")
            print("   - Right-click Command Prompt")
            print("   - Select 'Run as administrator'")
            print("   - Run the script again")
            
            print("\n5. CHECK DEVICE MANAGER:")
            print("   - Press Windows + X")
            print("   - Select 'Device Manager'")
            print("   - Look under 'Ports (COM & LPT)'")
            print("   - Make sure COM4 shows your ESP32 device")
            print("   - If there's a yellow warning, update the driver")
            
            print("\n" + "=" * 70)
            input("\nPress Enter after closing Arduino IDE Serial Monitor, then run the script again...")
            return
        
        # Increase buffer size for large files
        ser.reset_input_buffer()  # Clear any existing data
        time.sleep(2)  # Wait for connection to stabilize
        print("✓ Connected successfully!\n")
        print("=" * 70)
        print("Monitoring Serial output...")
        print("=" * 70)
        print("💡 The script will automatically capture CSV data when you type 'dump'")
        print("💡 Or wait for CSV data markers [CSV_START] and [CSV_END]")
        print("💡 Press Ctrl+C to stop\n")
        
        csv_data = []
        capturing = False
        last_data_time = time.time()
        lines_captured = 0
        
        # Optionally send 'dump' command automatically after a delay
        print("⏳ Waiting 3 seconds, then sending 'dump' command automatically...")
        time.sleep(3)
        ser.write(b'dump\n')
        ser.flush()  # Ensure command is sent
        print("✓ Sent 'dump' command to ESP32\n")
        
        print("📊 Capturing CSV data...\n")
        print("💡 For large files (3000+ lines), this may take 30-60 seconds...\n")
        
        csv_end_received = False
        no_data_timeout = 5  # Wait 5 seconds after last data before finalizing
        
        while True:
            # Read all available data
            if ser.in_waiting > 0:
                try:
                    # Read in larger chunks for better performance
                    raw_data = ser.read(ser.in_waiting)
                    text = raw_data.decode('utf-8', errors='ignore')
                    
                    # Process line by line
                    for line in text.splitlines():
                        line = line.strip()
                        if not line:
                            continue
                        
                        # Print to console for monitoring (limit output for large files)
                        if lines_captured < 50 or lines_captured % 100 == 0:
                            print(f"📥 Line {lines_captured + 1}: {line[:80]}..." if len(line) > 80 else f"📥 Line {lines_captured + 1}: {line}")
                        
                        # Check for CSV start marker
                        if "[CSV_START]" in line:
                            capturing = True
                            csv_data = []
                            csv_end_received = False
                            lines_captured = 0
                            print("\n🎯 CSV capture started!\n")
                            continue
                        
                        # Check for CSV end marker
                        if "[CSV_END]" in line:
                            csv_end_received = True
                            capturing = False
                            print(f"\n✅ CSV end marker received! (Captured {len(csv_data)} lines)")
                            print("⏳ Waiting 3 seconds to ensure all data is received...\n")
                            time.sleep(3)  # Wait a bit more for any remaining data
                            # Continue to process below
                        
                        # If capturing, save CSV lines
                        if capturing:
                            # Skip metadata lines (File:, Size:, etc.)
                            if line.startswith("File:") or line.startswith("Size:") or (line.startswith("bytes") and not ',' in line):
                                continue
                            # Save actual CSV data (lines with commas)
                            if ',' in line:
                                # Validate CSV line has correct number of columns (5: timestamp, time_s, current, temp, heater)
                                columns = line.split(',')
                                
                                # Check if line has proper structure
                                if len(columns) >= 4:  # At least 4 columns (timestamp might be missing)
                                    # Try to fix common issues
                                    fixed_line = fix_csv_line(line, columns)
                                    if fixed_line:
                                        csv_data.append(fixed_line)
                                        lines_captured += 1
                                        last_data_time = time.time()
                                    else:
                                        # Skip malformed lines
                                        if lines_captured < 10 or lines_captured % 500 == 0:
                                            print(f"⚠ Skipping malformed line: {line[:60]}...")
                                else:
                                    # Line has too few columns, skip it
                                    if lines_captured < 10 or lines_captured % 500 == 0:
                                        print(f"⚠ Skipping incomplete line (only {len(columns)} columns): {line[:60]}...")
                    
                    # If we received CSV_END, process and save
                    if csv_end_received and not capturing:
                        print(f"\n📊 Finalizing capture... (Total: {len(csv_data)} lines)")
                        
                        # Save CSV file
                        if csv_data:
                            try:
                                print("💾 Saving to file...")
                                with open(csv_filename, 'w', newline='', encoding='utf-8') as f:
                                    for csv_line in csv_data:
                                        f.write(csv_line + '\n')
                                
                                file_size = os.path.getsize(csv_filename)
                                print("=" * 70)
                                print(f"✅ CSV file saved successfully!")
                                print(f"📁 Location: {csv_filename}")
                                print(f"📊 Size: {file_size:,} bytes")
                                print(f"📝 Lines: {len(csv_data):,}")
                                print("=" * 70)
                                
                                # Verify file was written correctly
                                with open(csv_filename, 'r', encoding='utf-8') as f:
                                    verify_lines = sum(1 for _ in f)
                                    # Also check for malformed lines
                                    f.seek(0)
                                    malformed_count = 0
                                    for verify_line in f:
                                        cols = verify_line.strip().split(',')
                                        if len(cols) != 5:
                                            malformed_count += 1
                                
                                print(f"✓ Verified: {verify_lines:,} lines in file")
                                
                                if verify_lines != len(csv_data):
                                    print(f"⚠ Warning: File has {verify_lines} lines but captured {len(csv_data)} lines")
                                
                                if malformed_count > 0:
                                    print(f"⚠ Warning: {malformed_count} lines have incorrect column count (may need manual fixing)")
                                else:
                                    print(f"✓ All lines have correct format (5 columns each)")
                                
                                print("\n💡 You can now:")
                                print("   1. Type 'dump' again to capture updated data")
                                print("   2. Press Ctrl+C to exit")
                                print()
                                
                                # Clear data for next capture
                                csv_data = []
                                csv_end_received = False
                                capturing = False
                            except Exception as e:
                                print(f"❌ Error saving file: {e}")
                                import traceback
                                traceback.print_exc()
                        else:
                            print("⚠ No CSV data captured!")
                        csv_end_received = False  # Reset for next capture
                        
                except UnicodeDecodeError:
                    continue
                except Exception as e:
                    print(f"⚠ Warning: {e}")
            else:
                # No data available
                if capturing and not csv_end_received:
                    # Check if we've been waiting too long (might indicate connection issue)
                    if time.time() - last_data_time > 30:  # 30 seconds without data
                        print(f"\n⚠ Warning: No data received for 30 seconds!")
                        print(f"   Captured {len(csv_data)} lines so far...")
                        print("   Waiting for more data or [CSV_END] marker...")
                        last_data_time = time.time()  # Reset timer
            
            # Small delay to prevent CPU spinning
            time.sleep(0.01)
                
    except serial.SerialException as e:
        print("=" * 70)
        print("❌ SERIAL PORT ERROR!")
        print("=" * 70)
        print(f"\nError: {e}")
        print("\n🔧 QUICK FIX:")
        print("1. Close Arduino IDE Serial Monitor completely")
        print("2. Wait 2-3 seconds")
        print("3. Run this script again")
        print("\n" + "=" * 70)
        input("\nPress Enter to exit...")
    except KeyboardInterrupt:
        print(f"\n\n👋 Script stopped.")
        if csv_data:
            print(f"⚠ Warning: {len(csv_data)} lines were captured but not saved.")
            print("   The capture was interrupted before [CSV_END] marker.")
        input("Press Enter to exit...")
    except Exception as e:
        print(f"❌ Error: {e}")
        input("\nPress Enter to exit...")
    finally:
        if 'ser' in locals() and ser.is_open:
            ser.close()
            print("✓ Serial port closed")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n👋 Goodbye!")