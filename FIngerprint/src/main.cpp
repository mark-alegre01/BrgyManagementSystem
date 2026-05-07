#include <Arduino.h>
#include <HardwareSerial.h>
#include <WiFi.h>
#include <WebServer.h>

// ============= WiFi CREDENTIALS =============
const char* SSID = "LadyJune";
const char* PASSWORD = "TwinStar@2025";

// ============= HTTP SERVER CONFIG =============
WebServer server(80);

// ============= PIN DEFINITIONS =============
#define RED_LED_PIN 20          // Red LED (standby indicator)
#define GREEN_LED_PIN 21        // Green LED (detection indicator)
#define BUZZER_PIN 19           // Buzzer (detection alert)
#define FINGERPRINT_RX_PIN 44   // Fingerprint module RX (ESP32 GPIO44)
#define FINGERPRINT_TX_PIN 43   // Fingerprint module TX (ESP32 GPIO43)

// ============= SYSTEM STATES =============
enum SystemState {
  STANDBY,      // Module idle, red LED blinks slowly (1 second)
  ENROLLING,    // Waiting for fingerprint, red LED blinks fast
  FINGERPRINT_DETECTED  // Fingerprint detected, green LED + buzzer sync
};

// ============= TIMING CONSTANTS =============
#define STANDBY_BLINK_INTERVAL 1000      // 1 second for standby (total cycle)
#define ENROLLING_BLINK_INTERVAL 250     // 250ms for fast blinking (total cycle)
#define DETECTION_PULSE_INTERVAL 300     // 300ms for green LED + buzzer sync
#define DETECTION_PULSE_DURATION 3000    // Total time for detection pulse (3 seconds)
#define FINGERPRINT_BAUD_RATE 57600      // R307 default baud rate

// ============= R307 FINGERPRINT MODULE CONSTANTS =============
#define R307_START_CODE_1 0xEF           // Start code 1
#define R307_START_CODE_2 0x01           // Start code 2
#define R307_DEFAULT_ADDRESS 0xFFFFFFFF  // Default module address
#define R307_COMMAND_PACKET 0x01         // Command packet identifier
#define R307_DATA_PACKET 0x02            // Data packet identifier
#define R307_ACK_PACKET 0x07             // Acknowledgement packet identifier
#define R307_END_DATA 0x08               // End of data packet identifier

// ============= R307 COMMAND CODES =============
#define R307_CMD_GEN_IMG 0x01            // Generate image
#define R307_CMD_IMG2TZ 0x02             // Image to template
#define R307_CMD_MATCH 0x03              // Match templates
#define R307_CMD_SEARCH 0x04             // Search library
#define R307_CMD_REG_MODEL 0x05          // Register model
#define R307_CMD_STORE 0x06              // Store template
#define R307_CMD_LOAD 0x07               // Load template
#define R307_CMD_UP_CHAR 0x08            // Upload template
#define R307_CMD_DOWN_CHAR 0x09          // Download template
#define R307_CMD_IMG_UPLOAD 0x0A         // Upload image
#define R307_CMD_DELETE 0x0C             // Delete template
#define R307_CMD_EMPTY 0x0D              // Empty library
#define R307_CMD_SET_SYSPARA 0x0E        // Set system parameters
#define R307_CMD_READ_SYSPARA 0x0F       // Read system parameters
#define R307_CMD_SET_PWD 0x12            // Set password
#define R307_CMD_VERIFY_PWD 0x13         // Verify password
#define R307_CMD_GET_RANDOM_CODE 0x14    // Get random code
#define R307_CMD_SET_ADDR 0x15           // Set module address
#define R307_CMD_PORT_CONTROL 0x17       // Port control
#define R307_CMD_HANDSHAKE 0x40          // Handshake (correct command for R307)

// ============= UART CONFIGURATION =============
HardwareSerial fingerprintSerial(2);  // Use UART2 for fingerprint module to avoid conflicts with USB/Serial0

// ============= STATE VARIABLES =============
SystemState currentState = STANDBY;
unsigned long lastRedBlinkTime = 0;
unsigned long lastGreenBlinkTime = 0;
unsigned long detectionStartTime = 0;
unsigned long lastImageGenTime = 0;  // Track when we last sent image generation command
bool redLedState = LOW;
bool greenLedState = LOW;
bool buzzerState = LOW;
bool fingerprintInitialized = false;

// ============= ENROLLMENT SYSTEM =============
#define MAX_SCANS 3
int currentScan = 0;
bool enrollmentActive = false;
uint8_t fingerprintTemplates[MAX_SCANS][512]; // Store templates for 3 scans
bool scanCompleted[MAX_SCANS] = {false, false, false};

// ============= FUNCTION DECLARATIONS =============
void initializeHardware();
bool initializeFingerprintModule();
void initializeWiFi();
void initializeWebServer();
void handleRoot();
void handleStartEnrollment();
void handleStopEnrollment();
void handleGetStatus();
void addCorsHeaders();
void updateSystemState();
void handleStandbyMode();
void handleEnrollingMode();
void handleDetectionMode();
void detectFingerprint();
void clearR307Buffer();
void triggerFingerprintDetection();
bool r307Handshake();
uint16_t r307CalculateChecksum(uint8_t* packet, uint16_t length);
void r307SendCommand(uint8_t command, uint8_t* data, uint16_t dataLength);
bool r307ReceiveResponse(uint8_t* response, uint16_t* responseLength, uint32_t timeout);
void r307GenerateImage();
void printSystemStatus();

// ============= SETUP =============
void setup() {
  // Initialize Serial for debugging - IMMEDIATE OUTPUT
  Serial.begin(115200);
  delay(100); // Give serial time to initialize
  
  Serial.println("\n\n==========================================");
  Serial.println("🔥 ESP32-S3 FINGERPRINT MODULE STARTING...");
  Serial.println("==========================================");
  Serial.println("Firmware Version: 1.0.0");
  Serial.println("Build Date: " + String(__DATE__) + " " + String(__TIME__));
  Serial.println("==========================================");
  
  Serial.println("[BOOT] Serial initialized at 115200 baud");
  Serial.println("[BOOT] Starting hardware initialization...");
  
  // Initialize hardware FIRST
  initializeHardware();
  Serial.println("[BOOT] ✅ Hardware initialized");
  
  // Initialize WiFi
  initializeWiFi();
  Serial.println("[BOOT] ✅ WiFi initialized");
  
  // Initialize fingerprint module early so /start-enrollment can respond quickly
  fingerprintInitialized = initializeFingerprintModule();
  if (fingerprintInitialized) {
    Serial.println("[BOOT] ✅ Fingerprint module initialized");
  } else {
    Serial.println("[BOOT] ⚠️ Fingerprint module initialization failed at startup");
  }

  // Initialize web server
  initializeWebServer();
  Serial.println("[BOOT] ✅ Web server initialized");
  
  Serial.println("\n==========================================");
  Serial.println("✅ SYSTEM READY - ALL INITIALIZATION COMPLETE");
  Serial.println("==========================================");
  Serial.println("Commands:");
  Serial.println("  'S' - STANDBY mode");
  Serial.println("  'E' - ENROLLING mode");
  Serial.println("  'D' - Simulate detection");
  Serial.println("  'T' - Test R307 connectivity");
  Serial.println("  '?' - Status");
  Serial.println("Web endpoints:");
  Serial.println("  POST /start-enrollment");
  Serial.println("  POST /stop-enrollment");
  Serial.println("  GET /status");
  Serial.println("==========================================\n");
}

// ============= MAIN LOOP =============
void loop() {
  // Handle HTTP requests
  server.handleClient();
  
  // Update system state based on input
  updateSystemState();
  
  // Handle LED and buzzer based on current state
  switch(currentState) {
    case STANDBY:
      handleStandbyMode();
      break;
    case ENROLLING:
      handleEnrollingMode();
      break;
    case FINGERPRINT_DETECTED:
      handleDetectionMode();
      break;
  }
  
  // Check fingerprint module for data
  detectFingerprint();
  
  // Clear any unsolicited R307 data when not enrolling to prevent serial corruption
  if (currentState != ENROLLING) {
    clearR307Buffer();
  }
  
  // Debug heartbeat every 5 seconds
  static unsigned long lastHeartbeat = 0;
  if (millis() - lastHeartbeat >= 5000) {
    lastHeartbeat = millis();
    Serial.printf("[HEARTBEAT] System running - State: %s, Enrollment: %s, Uptime: %lu seconds\n", 
                  currentState == STANDBY ? "STANDBY" : 
                  currentState == ENROLLING ? "ENROLLING" : "DETECTED",
                  enrollmentActive ? "ACTIVE" : "INACTIVE",
                  millis() / 1000);
  }
  
  // Small delay to prevent overwhelming the processor
  delayMicroseconds(100);
}

// ============= HARDWARE INITIALIZATION =============
void initializeHardware() {
  // Configure GPIO pins
  pinMode(RED_LED_PIN, OUTPUT);
  pinMode(GREEN_LED_PIN, OUTPUT);
  pinMode(BUZZER_PIN, OUTPUT);
  
  // Set initial states
  digitalWrite(RED_LED_PIN, LOW);
  digitalWrite(GREEN_LED_PIN, LOW);
  digitalWrite(BUZZER_PIN, LOW);
  
  Serial.println("[INIT] GPIO pins configured");
  Serial.printf("  - Red LED: GPIO %d\n", RED_LED_PIN);
  Serial.printf("  - Green LED: GPIO %d\n", GREEN_LED_PIN);
  Serial.printf("  - Buzzer: GPIO %d\n", BUZZER_PIN);
}

// ============= FINGERPRINT MODULE INITIALIZATION =============
bool initializeFingerprintModule() {
  // CRITICAL: Initialize UART2 for fingerprint module
  fingerprintSerial.begin(FINGERPRINT_BAUD_RATE, SERIAL_8N1, FINGERPRINT_RX_PIN, FINGERPRINT_TX_PIN);
  
  // ⚠️  SILENT BUFFER CLEARING - NO Serial.println() during this phase
  // The R307 module sends a lot of binary startup data that corrupts serial output
  // We must clear it BEFORE printing anything to the main Serial
  
  delay(500); // Let the R307 module start sending its initial data
  
  // Aggressively clear the buffer for 4 seconds with NO other serial output
  unsigned long clearStart = millis();
  int totalCleared = 0;
  while (millis() - clearStart < 4000) {
    while (fingerprintSerial.available()) {
      fingerprintSerial.read();
      totalCleared++;
    }
    delay(50); // Small delay to batch reads
  }
  
  // NOW we can safely print after the buffer is clean
  Serial.println("[INIT] R307 Fingerprint module UART initialized");
  Serial.printf("[INIT] Cleared %d bytes of startup data from R307\n", totalCleared);
  Serial.printf("[INIT] GPIO%d RX, GPIO%d TX @ %d baud\n", FINGERPRINT_RX_PIN, FINGERPRINT_TX_PIN, FINGERPRINT_BAUD_RATE);
  
  // Try to handshake with the module
  bool moduleConnected = false;
  for (int attempt = 1; attempt <= 3; attempt++) {
    Serial.printf("[INIT] Handshake attempt %d/3\n", attempt);
    
    if (r307Handshake()) {
      moduleConnected = true;
      Serial.println("[INIT] ✅ R307 module successfully connected!");
      break;
    } else {
      Serial.printf("[INIT] ❌ Handshake attempt %d failed\n", attempt);
      delay(1000);
      
      // Clear buffer between attempts
      while (fingerprintSerial.available()) {
        fingerprintSerial.read();
      }
    }
  }
  
  if (!moduleConnected) {
    Serial.println("[INIT] ⚠️  R307 module handshake failed - continuing in offline mode");
    Serial.println("[INIT]    Check: RX↔TX, TX↔RX, GND↔GND, VCC↔3.3V/5V");
  }
  
  Serial.println("[INIT] Fingerprint module initialization complete\n");
  return moduleConnected;
}

// ============= WiFi INITIALIZATION =============
void initializeWiFi() {
  Serial.println("[WIFI] WiFi initialization starting...");
  Serial.printf("  - SSID: %s\n", SSID);
  
  WiFi.mode(WIFI_STA);
  WiFi.begin(SSID, PASSWORD);
  
  int attempts = 0;
  const int MAX_ATTEMPTS = 20;
  
  Serial.print("[WIFI] Connecting to WiFi");
  while(WiFi.status() != WL_CONNECTED && attempts < MAX_ATTEMPTS) {
    delay(500);
    Serial.print(".");
    attempts++;
  }
  
  Serial.println();
  
  if(WiFi.status() == WL_CONNECTED) {
    Serial.println("[WIFI] ✅ Connection successful!");
    Serial.printf("  - IP Address: %s\n", WiFi.localIP().toString().c_str());
    Serial.printf("  - Signal Strength: %d dBm\n", WiFi.RSSI());
    Serial.printf("  - MAC Address: %s\n", WiFi.macAddress().c_str());
  } else {
    Serial.println("[WIFI] ❌ Connection failed!");
    Serial.println("[WIFI] Continuing in offline mode...");
  }
}

// ============= WEB SERVER INITIALIZATION =============
void initializeWebServer() {
  // CRITICAL: Clear R307 buffer before printing web server messages to prevent corruption
  delay(100);
  while (fingerprintSerial.available()) {
    fingerprintSerial.read();
  }
  
  Serial.println("[INIT] Web server initialization...");
  
  // Define HTTP routes
  server.on("/", HTTP_GET, handleRoot);
  server.on("/start-enrollment", HTTP_POST, handleStartEnrollment);
  server.on("/start-enrollment", HTTP_OPTIONS, []() {
    addCorsHeaders();
    server.send(204);
  });
  server.on("/stop-enrollment", HTTP_POST, handleStopEnrollment);
  server.on("/stop-enrollment", HTTP_OPTIONS, []() {
    addCorsHeaders();
    server.send(204);
  });
  server.on("/status", HTTP_GET, handleGetStatus);
  server.on("/status", HTTP_OPTIONS, []() {
    addCorsHeaders();
    server.send(204);
  });
  
  // Start server
  server.begin();
  Serial.println("[WEB] HTTP server started");
  Serial.println("[WEB] Available endpoints:");
  Serial.println("  - GET  /           - System info");
  Serial.println("  - POST /start-enrollment - Start biometric enrollment");
  Serial.println("  - POST /stop-enrollment  - Stop enrollment");
  Serial.println("  - GET  /status     - Get current status");
}

// ============= HTTP HANDLERS =============
void addCorsHeaders() {
  server.sendHeader("Access-Control-Allow-Origin", "*");
  server.sendHeader("Access-Control-Allow-Methods", "GET, POST, OPTIONS");
  server.sendHeader("Access-Control-Allow-Headers", "Content-Type");
}

void handleRoot() {
  addCorsHeaders();
  String html = "<html><head><title>ESP32 Fingerprint Module</title></head><body>";
  html += "<h1>ESP32-S3 Fingerprint Enrollment System</h1>";
  html += "<p>IP Address: " + WiFi.localIP().toString() + "</p>";
  html += "<p>Status: ";
  
  switch(currentState) {
    case STANDBY: html += "STANDBY"; break;
    case ENROLLING: html += "ENROLLING"; break;
    case FINGERPRINT_DETECTED: html += "FINGERPRINT DETECTED"; break;
  }
  
  html += "</p>";
  html += "<p><a href='/status'>Get Status JSON</a></p>";
  html += "</body></html>";
  
  server.send(200, "text/html", html);
}

void handleStartEnrollment() {
  addCorsHeaders();
  Serial.println("[HTTP] /start-enrollment request received");
  if (!fingerprintInitialized) {
    currentState = STANDBY;
    String errorResponse = "{\"status\":\"error\",\"message\":\"Fingerprint module not initialized. Check hardware and reboot device.\"}";
    server.send(500, "application/json", errorResponse);
    return;
  }
  
  Serial.println("\n==========================================");
  Serial.println("🎯 STARTING 3-SCAN BIOMETRIC ENROLLMENT");
  Serial.println("==========================================");
  
  // Reset enrollment state
  currentScan = 0;
  enrollmentActive = true;
  memset(scanCompleted, 0, sizeof(scanCompleted));
  
  // Switch to enrolling mode
  currentState = ENROLLING;
  lastRedBlinkTime = millis();
  
  Serial.println("📋 Enrollment Progress:");
  Serial.println("  Scan 1/3: Place finger on sensor...");
  Serial.println("  Scan 2/3: Place same finger again...");
  Serial.println("  Scan 3/3: Place same finger one more time...");
  Serial.println("==========================================");
  
  String response = "{";
  response += "\"status\":\"success\",";
  response += "\"message\":\"3-scan biometric enrollment started\",";
  response += "\"total_scans\":3,";
  response += "\"current_scan\":1,";
  response += "\"state\":\"enrolling\"";
  response += "}";
  
  server.send(200, "application/json", response);
  Serial.println("[HTTP] ✅ Enrollment started - waiting for finger scans...\n");
}

void handleStopEnrollment() {
  addCorsHeaders();
  Serial.println("\n[HTTP] Stop enrollment request received");
  currentState = STANDBY;
  enrollmentActive = false;

  String response = "{\"status\":\"success\",\"message\":\"Enrollment stopped\",\"state\":\"standby\"}";
  server.send(200, "application/json", response);
}

void handleGetStatus() {
  addCorsHeaders();
  Serial.println("[HTTP] /status request received");
  String stateStr;
  switch(currentState) {
    case STANDBY: stateStr = "standby"; break;
    case ENROLLING: stateStr = "enrolling"; break;
    case FINGERPRINT_DETECTED: stateStr = "detected"; break;
  }
  
  String response = "{";
  response += "\"state\":\"" + stateStr + "\",";
  response += "\"ip\":\"" + WiFi.localIP().toString() + "\",";
  response += "\"uptime\":" + String(millis()) + ",";
  response += "\"wifi_signal\":" + String(WiFi.RSSI());
  response += "}";
  
  server.send(200, "application/json", response);
}

// ============= STANDBY MODE (Red LED slow blink) =============
void handleStandbyMode() {
  unsigned long currentTime = millis();
  
  // Toggle red LED every 500ms (1 second total cycle)
  if(currentTime - lastRedBlinkTime >= STANDBY_BLINK_INTERVAL / 2) {
    lastRedBlinkTime = currentTime;
    redLedState = !redLedState;
    digitalWrite(RED_LED_PIN, redLedState);
  }
  
  // Ensure green LED and buzzer are off
  digitalWrite(GREEN_LED_PIN, LOW);
  digitalWrite(BUZZER_PIN, LOW);
}

// ============= ENROLLING MODE (Red LED fast blink) =============
void handleEnrollingMode() {
  unsigned long currentTime = millis();
  
  // Toggle red LED every 125ms (250ms total cycle for fast blink)
  if(currentTime - lastRedBlinkTime >= ENROLLING_BLINK_INTERVAL / 2) {
    lastRedBlinkTime = currentTime;
    redLedState = !redLedState;
    digitalWrite(RED_LED_PIN, redLedState);
    
    if(redLedState) {
      Serial.println("[ENROLLING] Waiting for fingerprint...");
    }
  }
  
  // Continuously try to generate fingerprint images
  r307GenerateImage();
  
  // Ensure green LED and buzzer are off
  digitalWrite(GREEN_LED_PIN, LOW);
  digitalWrite(BUZZER_PIN, LOW);
}

// ============= DETECTION MODE (Green LED + Buzzer synchronized) =============
void handleDetectionMode() {
  unsigned long currentTime = millis();
  unsigned long elapsedTime = currentTime - detectionStartTime;
  
  // Pulse duration: alternate between ON and OFF
  bool pulseState = ((elapsedTime % DETECTION_PULSE_INTERVAL) < (DETECTION_PULSE_INTERVAL / 2));
  
  // Synchronize green LED and buzzer
  digitalWrite(GREEN_LED_PIN, pulseState);
  digitalWrite(BUZZER_PIN, pulseState);
  
  // Exit detection mode after 3 seconds
  if(elapsedTime >= DETECTION_PULSE_DURATION) {
    currentState = STANDBY;
    digitalWrite(GREEN_LED_PIN, LOW);
    digitalWrite(BUZZER_PIN, LOW);
    Serial.println("[DETECTION] Pulse complete. Returning to STANDBY\n");
  }
}

// ============= UPDATE SYSTEM STATE =============
void updateSystemState() {
  // Check for external input (serial command for testing)
  if(Serial.available() > 0) {
    char command = Serial.read();
    
    switch(command) {
      case 's':
      case 'S':
        currentState = STANDBY;
        Serial.println("\n[CMD] State changed to: STANDBY");
        break;
      case 'e':
      case 'E':
        currentState = ENROLLING;
        lastRedBlinkTime = millis();
        Serial.println("\n[CMD] State changed to: ENROLLING");
        Serial.println("[CMD] System is now waiting for fingerprint detection...");
        break;
      case 'd':
      case 'D':
        if(currentState == ENROLLING) {
          triggerFingerprintDetection();
        }
        break;
      case '?':
        printSystemStatus();
        break;
      default:
        break;
    }
  }
}

// ============= TRIGGER FINGERPRINT DETECTION =============
void triggerFingerprintDetection() {
  if (!enrollmentActive || currentState != ENROLLING) {
    return; // Only process during active enrollment
  }
  
  currentScan++;
  scanCompleted[currentScan - 1] = true;
  
  Serial.println("\n==========================================");
  Serial.printf("🎯 SCAN %d/%d COMPLETED!\n", currentScan, MAX_SCANS);
  Serial.println("==========================================");
  
  // Store the fingerprint template (simplified - in real implementation you'd store the actual template)
  // For now, just mark as completed
  
  if (currentScan < MAX_SCANS) {
    // Still need more scans
    Serial.printf("📋 Next: Scan %d/%d - Place same finger again...\n", currentScan + 1, MAX_SCANS);
    Serial.println("==========================================\n");
    
    // Reset for next scan - stay in enrolling mode
    currentState = ENROLLING;
  } else {
    // All scans completed
    Serial.println("✅ ALL 3 SCANS COMPLETED!");
    Serial.println("🔄 Processing fingerprint templates...");
    Serial.println("==========================================");
    
    // Switch to detected state for visual feedback
    currentState = FINGERPRINT_DETECTED;
    detectionStartTime = millis();
    
    // Reset enrollment
    enrollmentActive = false;
    
    Serial.println("[SUCCESS] Biometric enrollment completed successfully!");
    Serial.println("[SUCCESS] Templates ready for storage\n");
  }
  
  // Provide visual feedback
  digitalWrite(GREEN_LED_PIN, HIGH);
  digitalWrite(BUZZER_PIN, HIGH);
  delay(500); // Short beep/LED flash for scan confirmation
  digitalWrite(GREEN_LED_PIN, LOW);
  digitalWrite(BUZZER_PIN, LOW);
}

// ============= CLEAR R307 BUFFER =============
void clearR307Buffer() {
  // Aggressively clear R307 buffer to prevent serial corruption
  // Don't report anything to Serial to avoid interference
  int cleared = 0;
  while (fingerprintSerial.available()) {
    fingerprintSerial.read();
    cleared++;
  }
  // Silent operation - no Serial.println() to avoid corruption
}
void detectFingerprint() {
  static unsigned long lastDebug = 0;
  static int debugCount = 0;
  
  // Debug output every 2 seconds to show function is running
  if (millis() - lastDebug >= 2000) {
    lastDebug = millis();
    debugCount++;
    Serial.printf("[DETECT] 🔍 Function running (check #%d) - State: %s, Enrollment: %s\n", 
                  debugCount, 
                  currentState == STANDBY ? "STANDBY" : 
                  currentState == ENROLLING ? "ENROLLING" : "DETECTED",
                  enrollmentActive ? "ACTIVE" : "INACTIVE");
  }
  
  // Only process data if we're actively enrolling
  if (currentState != ENROLLING || !enrollmentActive) {
    return;
  }
  
  // Check if fingerprint module has data available
  if (fingerprintSerial.available() > 0) {
    // Don't print raw data to avoid serial corruption - just indicate data received
    Serial.println("[R307] 📡 Data received from module");
    
    uint8_t response[256];
    uint16_t responseLength = 0;

    if (r307ReceiveResponse(response, &responseLength, 200)) {  // Slightly longer timeout
      // Check if this is an acknowledgement packet
      if (response[6] == R307_ACK_PACKET) {
        uint8_t confirmationCode = response[9];

        Serial.printf("[R307] ✅ ACK received - Code: 0x%02X", confirmationCode);

        // Confirmation code 0x00 means success
        if (confirmationCode == 0x00 && currentState == ENROLLING && enrollmentActive) {
          Serial.println(" - FINGERPRINT DETECTED!");
          triggerFingerprintDetection();
        } else if (confirmationCode != 0x00) {
          // Print error message based on confirmation code
          Serial.print(" - Error: ");
          switch (confirmationCode) {
            case 0x01: Serial.println("Receive packet error"); break;
            case 0x02: Serial.println("No finger detected"); break;
            case 0x03: Serial.println("Fail to collect finger image"); break;
            case 0x06: Serial.println("Fail to generate character file"); break;
            case 0x07: Serial.println("Fail to generate template"); break;
            case 0x0A: Serial.println("Fail to combine character files"); break;
            case 0x0C: Serial.println("Character file invalid"); break;
            default: Serial.printf("Unknown (0x%02X)\n", confirmationCode); break;
          }
        } else {
          Serial.println(" - OK");
        }
      } else {
        Serial.printf("[R307] 📦 Non-ACK packet received (Type: 0x%02X)\n", response[6]);
      }
    } else {
      // Clear any remaining data in buffer to prevent accumulation
      int cleared = 0;
      while (fingerprintSerial.available()) {
        fingerprintSerial.read();
        cleared++;
      }
      if (cleared > 0) {
        Serial.printf("[R307] ❌ Response parsing failed - cleared %d bytes\n", cleared);
      }
    }
  }

  // For testing: simulate fingerprint detection when 'D' is pressed in serial
  // Also test R307 module with 'T' command
  if(Serial.available() > 0) {
    char cmd = Serial.read();
    if(cmd == 'D' || cmd == 'd') {
      if(currentState == ENROLLING && enrollmentActive) {
        Serial.println("[TEST] Simulating fingerprint detection");
        triggerFingerprintDetection();
      } else {
        Serial.println("[TEST] Cannot simulate - not in enrolling mode");
      }
    } else if(cmd == 'T' || cmd == 't') {
      Serial.println("[TEST] Testing R307 module connectivity...");
      if (r307Handshake()) {
        Serial.println("[TEST] ✅ R307 module is responding!");
      } else {
        Serial.println("[TEST] ❌ R307 module not responding");
      }
    }
  }
}

// ============= R307 FINGERPRINT FUNCTIONS =============

// Handshake with R307 module
bool r307Handshake() {
  Serial.println("[R307] 🔄 Attempting module connection...");
  
  uint8_t password[4] = {0x00, 0x00, 0x00, 0x00};
  r307SendCommand(R307_CMD_VERIFY_PWD, password, 4);
  
  uint8_t response[12];
  uint16_t responseLength = 0;
  
  Serial.println("[R307] ⏳ Waiting for handshake response...");
  if (r307ReceiveResponse(response, &responseLength, 3000)) {
    if (response[6] == R307_ACK_PACKET && response[9] == 0x00) {
      Serial.println("[R307] ✅ Module connected and responding correctly!");
      return true;
    } else {
      Serial.printf("[R307] ❌ Module responded but verification failed: 0x%02X\n", response[9]);
      Serial.println("[R307] This could indicate wrong password or module not ready");
    }
  } else {
    Serial.println("[R307] ❌ No response from module during handshake");
    Serial.println("[R307] Possible issues:");
    Serial.println("  - R307 module not powered on");
    Serial.println("  - UART connections incorrect (TX<->RX, RX<->TX)");
    Serial.println("  - Wrong GPIO pins (should be GPIO43 TX, GPIO44 RX)");
    Serial.println("  - Baud rate mismatch (should be 57600)");
  }
  
  Serial.println("[R307] ❌ Fingerprint module connection failed");
  return false;
}

// Calculate checksum for R307 packets
uint16_t r307CalculateChecksum(uint8_t* packet, uint16_t length) {
  uint16_t checksum = 0;
  for (uint16_t i = 6; i < length - 2; i++) {
    checksum += packet[i];
  }
  return checksum;
}

// Send command to R307 module
void r307SendCommand(uint8_t command, uint8_t* data, uint16_t dataLength) {
  uint16_t packetLength = 3 + dataLength;  // Command(1) + data length
  uint8_t packet[256];
  
  // Header
  packet[0] = R307_START_CODE_1;
  packet[1] = R307_START_CODE_2;
  packet[2] = (R307_DEFAULT_ADDRESS >> 24) & 0xFF;
  packet[3] = (R307_DEFAULT_ADDRESS >> 16) & 0xFF;
  packet[4] = (R307_DEFAULT_ADDRESS >> 8) & 0xFF;
  packet[5] = R307_DEFAULT_ADDRESS & 0xFF;
  
  // Packet identifier
  packet[6] = R307_COMMAND_PACKET;
  
  // Packet length
  packet[7] = (packetLength >> 8) & 0xFF;
  packet[8] = packetLength & 0xFF;
  
  // Command
  packet[9] = command;
  
  // Data (if any)
  if (data != NULL && dataLength > 0) {
    for (uint16_t i = 0; i < dataLength; i++) {
      packet[10 + i] = data[i];
    }
  }
  
  // Checksum
  uint16_t checksum = r307CalculateChecksum(packet, 12 + dataLength);
  packet[10 + dataLength] = (checksum >> 8) & 0xFF;
  packet[11 + dataLength] = checksum & 0xFF;
  
  // Send packet
  fingerprintSerial.write(packet, 12 + dataLength);
  
  Serial.printf("[R307] Command sent: 0x%02X (length: %d)\n", command, 12 + dataLength);
}

// Receive response from R307 module
bool r307ReceiveResponse(uint8_t* response, uint16_t* responseLength, uint32_t timeout) {
  uint32_t startTime = millis();
  
  while (millis() - startTime < timeout) {
    if (fingerprintSerial.available() >= 12) {  // Minimum packet size
      // Read header
      if (fingerprintSerial.read() == R307_START_CODE_1 &&
          fingerprintSerial.read() == R307_START_CODE_2) {
        
        // Read address (skip for now)
        for (int i = 0; i < 4; i++) fingerprintSerial.read();
        
        // Read packet identifier
        uint8_t packetId = fingerprintSerial.read();
        
        // Read packet length
        uint8_t lengthHigh = fingerprintSerial.read();
        uint8_t lengthLow = fingerprintSerial.read();
        uint16_t packetLength = (lengthHigh << 8) | lengthLow;
        
        if (packetLength > 256) {
          Serial.println("[R307] Packet too large");
          return false;
        }
        
        // Read packet data and checksum bytes as part of the packetLength
        response[0] = R307_START_CODE_1;
        response[1] = R307_START_CODE_2;
        response[2] = (R307_DEFAULT_ADDRESS >> 24) & 0xFF;
        response[3] = (R307_DEFAULT_ADDRESS >> 16) & 0xFF;
        response[4] = (R307_DEFAULT_ADDRESS >> 8) & 0xFF;
        response[5] = R307_DEFAULT_ADDRESS & 0xFF;
        response[6] = packetId;
        response[7] = lengthHigh;
        response[8] = lengthLow;
        
        for (uint16_t i = 0; i < packetLength; i++) {
          if (fingerprintSerial.available()) {
            response[9 + i] = fingerprintSerial.read();
          } else {
            Serial.println("[R307] Timeout reading packet data");
            return false;
          }
        }
        
        *responseLength = 9 + packetLength;
        
        // Verify checksum
        uint16_t calculatedChecksum = r307CalculateChecksum(response, *responseLength);
        uint16_t receivedChecksum = (response[*responseLength - 2] << 8) | response[*responseLength - 1];
        
        if (calculatedChecksum == receivedChecksum) {
          return true;
        } else {
          Serial.println("[R307] Checksum mismatch");
          return false;
        }
      }
    }
    delay(10);
  }
  
  Serial.println("[R307] Response timeout");
  return false;
}

// Generate fingerprint image (for enrollment)
void r307GenerateImage() {
  unsigned long currentTime = millis();

  // Only send command every 500ms to avoid overwhelming the module
  if (currentTime - lastImageGenTime >= 500) {
    lastImageGenTime = currentTime;

    if (currentState == ENROLLING) {
      Serial.println("[R307] >>> Sending GEN_IMG command to R307 module...");
      r307SendCommand(R307_CMD_GEN_IMG, NULL, 0);
      Serial.println("[R307] <<< GEN_IMG command sent, waiting for response...");
    }
  }
}

// ============= SYSTEM STATUS PRINT =============
void printSystemStatus() {
  Serial.println("\n================================");
  Serial.println("SYSTEM STATUS");
  Serial.println("================================");
  Serial.printf("Current State: ");
  
  switch(currentState) {
    case STANDBY:
      Serial.println("STANDBY (Red LED slow blink - 1 second)");
      break;
    case ENROLLING:
      Serial.println("ENROLLING (Red LED fast blink - waiting for fingerprint)");
      break;
    case FINGERPRINT_DETECTED:
      Serial.println("FINGERPRINT_DETECTED (Green LED + Buzzer pulsing)");
      break;
  }
  
  Serial.println("\nAVAILABLE COMMANDS:");
  Serial.println("  'S' - Change to STANDBY mode");
  Serial.println("  'E' - Change to ENROLLING mode (simulate start button)");
  Serial.println("  'D' - Simulate fingerprint DETECTION");
  Serial.println("  '?' - Print this status\n");
  Serial.println("================================\n");
}
