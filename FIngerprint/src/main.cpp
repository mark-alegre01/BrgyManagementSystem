#include <Arduino.h>
#include <HardwareSerial.h>
#include <WiFi.h>
#include <WebServer.h>

// ============= WiFi CREDENTIALS =============
const char* SSID = "LadyJune";
const char* PASSWORD = "TwinStar@2025";

// ============= WiFi STATIC IP CONFIG =============
IPAddress local_IP(192, 168, 1, 55);
IPAddress gateway(192, 168, 1, 1);
IPAddress subnet(255, 255, 255, 0);
IPAddress primaryDNS(8, 8, 8, 8);   // Optional: Google DNS
IPAddress secondaryDNS(8, 8, 4, 4); // Optional: Google DNS

// ============= HTTP SERVER CONFIG =============
WebServer server(80);

// ============= PIN DEFINITIONS =============
#define RED_LED_PIN 18          // Label D18
#define GREEN_LED_PIN 27        // MOVED FROM 19 TO 27 TO AVOID CONFLICTS
#define BLUE_LED_PIN 5          // Label D5
#define BUZZER_PIN 4            // MOVED BACK TO PIN 4 AS REQUESTED
#define FINGERPRINT_RX_PIN 22   // GPIO22 (D22) <- Sensor TX (Green)
#define FINGERPRINT_TX_PIN 23   // GPIO23 (D23) -> Sensor RX (White)

// ============= SYSTEM STATES =============
enum SystemState {
  STANDBY,      // Module idle, red LED blinks slowly (1 second)
  ENROLLING,    // Waiting for fingerprint, red LED blinks fast
  VERIFYING,    // Waiting for login fingerprint, red LED blinks fast
  WAIT_REMOVE,  // Success! Wait for finger to be removed
  FINGERPRINT_DETECTED,  // Fingerprint detected, green LED + buzzer sync
  AUTH_FAILED          // Error feedback (Red LED + 3 beeps)
};

// ============= TIMING CONSTANTS =============
#define STANDBY_BLINK_INTERVAL 1000      // 1 second for standby (total cycle)
#define ENROLLING_BLINK_INTERVAL 250     // 250ms for fast blinking (total cycle)
#define DETECTION_PULSE_INTERVAL 300     // 300ms for green LED + buzzer sync
#define DETECTION_PULSE_DURATION 3000    // Total time for detection pulse (3 seconds)
#define FINGERPRINT_BAUD_RATE 57600      // R307 default baud rate

#define BUZZER_LEDC_CHANNEL 3
#define BUZZER_TONE_HZ 3500
#define BUZZER_DUTY 128
#define BUZZER_PULSE_DURATION 200 // 200ms short beep

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
HardwareSerial fingerprintSerial(2);  // Use UART2 for the sensor (keeps USB Serial free)

// ============= STATE VARIABLES =============
SystemState currentState = STANDBY;
unsigned long lastRedBlinkTime = 0;
unsigned long lastGreenBlinkTime = 0;
unsigned long detectionStartTime = 0;
unsigned long lastImageGenTime = 0;  // Track when we last sent image generation command
bool redLedState = LOW;
bool greenLedState = LOW;
bool buzzerState = LOW;
bool buzzerPulseActive = false;
unsigned long buzzerPulseStartTime = 0;
bool fingerprintInitialized = false;
String lastErrorMessage = "Ready";
bool authFailedResetPending = false; // Flag to reset the error beeper
bool isBeeping = false; // Hardware-level lockout to prevent beep restarts

// ============= FINGERPRINT DATA =============
int enrollmentSlotID = 0;
int matchedFingerprintID = 0;

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
void handleStartVerification();
void handleDeleteFingerprint();
void handleEmptyLibrary();
void handleErrorFeedback();
void handleStopEnrollment();
void handleGetStatus();
void addCorsHeaders();
void updateSystemState();
void handleStandbyMode();
void handleEnrollingMode();
void handleDetectionMode();
void detectFingerprint();
void handleFailMode();
void clearR307Buffer();
void triggerFingerprintDetection();
bool r307Handshake();
uint16_t r307CalculateChecksum(uint8_t* packet, uint16_t length);
void r307SendCommand(uint8_t command, uint8_t* data, uint16_t dataLength);
bool r307ReceiveResponse(uint8_t* response, uint16_t* responseLength, uint32_t timeout);
uint8_t r307GenerateImage();
uint8_t r307Img2Tz(uint8_t slot);
uint8_t r307RegModel();
uint8_t r307StoreModel(uint16_t id);
uint8_t r307Search(uint8_t bufferId, uint16_t* fingerID, uint16_t* score);
void triggerAuthFailed(String reason);
void printSystemStatus();
void setLeds(bool red, bool green, bool blue);

// ============= SETUP =============
void setup() {
  Serial.begin(115200);
  initializeHardware();
  initializeWiFi();
  digitalWrite(BLUE_LED_PIN, HIGH);
  fingerprintInitialized = initializeFingerprintModule();
  initializeWebServer();
}

// ============= MAIN LOOP =============
void loop() {
  server.handleClient();
  updateSystemState();
  
  switch(currentState) {
    case STANDBY:
      handleStandbyMode();
      break;
    case ENROLLING:
      handleEnrollingMode();
      break;
    case VERIFYING:
      handleEnrollingMode();
      break;
    case WAIT_REMOVE:
      handleEnrollingMode(); // Keep blinking while waiting
      break;
    case FINGERPRINT_DETECTED:
      handleDetectionMode();
      break;
    case AUTH_FAILED:
      handleFailMode();
      break;
  }
  
  detectFingerprint();
  
  if (currentState != ENROLLING && currentState != VERIFYING) {
    clearR307Buffer();
  }

  // Only handle buzzer pulse if NOT in error/fail mode (auth failed produces its own tones)
  if (buzzerPulseActive && currentState != AUTH_FAILED) {
    if (millis() - buzzerPulseStartTime >= BUZZER_PULSE_DURATION) {
      buzzerPulseActive = false;
      ledcWriteTone(BUZZER_LEDC_CHANNEL, 0);
    }
  }
  
  delayMicroseconds(100);
}

// ============= HARDWARE INITIALIZATION =============
void initializeHardware() {
  // Initialize LED pins
  pinMode(RED_LED_PIN, OUTPUT);
  pinMode(GREEN_LED_PIN, OUTPUT);
  pinMode(BLUE_LED_PIN, OUTPUT);
  pinMode(BUZZER_PIN, OUTPUT);

  // Initialize buzzer with PWM
  ledcSetup(BUZZER_LEDC_CHANNEL, BUZZER_TONE_HZ, 8);
  ledcAttachPin(BUZZER_PIN, BUZZER_LEDC_CHANNEL);
  
  // Set all to LOW/OFF state
  setLeds(false, false, false);
  
  // HARDWARE TEST: Cycle all LEDs and beep to verify wiring
  Serial.println("[BOOT] Starting Hardware Self-Test...");
  
  setLeds(true, false, false); // Red
  delay(300);
  setLeds(false, true, false); // Green
  delay(300);
  setLeds(false, false, true); // Blue
  delay(300);
  
  // Beep + Green
  setLeds(false, true, false);
  ledcWriteTone(BUZZER_LEDC_CHANNEL, BUZZER_TONE_HZ);
  ledcWrite(BUZZER_LEDC_CHANNEL, 150);
  delay(200);
  ledcWriteTone(BUZZER_LEDC_CHANNEL, 0);
  setLeds(false, false, false);
  
  Serial.println("[BOOT] Hardware test complete.");
  
  delay(100); // Give hardware time to stabilize
}

// ============= LED CONTROL UTILITY =============
void setLeds(bool red, bool green, bool blue) {
  digitalWrite(RED_LED_PIN, red ? HIGH : LOW);
  digitalWrite(GREEN_LED_PIN, green ? HIGH : LOW);
  digitalWrite(BLUE_LED_PIN, blue ? HIGH : LOW);
}

// ============= FINGERPRINT MODULE INITIALIZATION =============
bool initializeFingerprintModule() {
  if (fingerprintInitialized) return true; // Early exit if already OK
  fingerprintSerial.begin(FINGERPRINT_BAUD_RATE, SERIAL_8N1, FINGERPRINT_RX_PIN, FINGERPRINT_TX_PIN);
  delay(500); 
  unsigned long clearStart = millis();
  while (millis() - clearStart < 500) {
    while (fingerprintSerial.available()) {
      fingerprintSerial.read();
    }
    delay(50);
  }
  
  uint8_t password[4] = {0x00, 0x00, 0x00, 0x00};
  long bauds[] = {57600, 9600, 115200};
  uint8_t rxPins[] = {FINGERPRINT_RX_PIN, FINGERPRINT_TX_PIN};
  uint8_t txPins[] = {FINGERPRINT_TX_PIN, FINGERPRINT_RX_PIN};

  for (int p = 0; p < 2; p++) {
    uint8_t currentRX = rxPins[p];
    uint8_t currentTX = txPins[p];

    for (int b = 0; b < 3; b++) {
      long currentBaud = bauds[b];
      pinMode(currentRX, INPUT_PULLUP);
      fingerprintSerial.begin(currentBaud, SERIAL_8N1, currentRX, currentTX);
      delay(200);
      while(fingerprintSerial.available()) fingerprintSerial.read();
      uint8_t response[64];
      uint16_t respLen = 0;

      r307SendCommand(R307_CMD_VERIFY_PWD, password, 4);
      if (r307ReceiveResponse(response, &respLen, 700)) {
        if (response[6] == R307_ACK_PACKET && response[9] == 0x00) {
          fingerprintInitialized = true;
          lastErrorMessage = "Fingerprint online";
          return true;
        }
      }
      r307SendCommand(R307_CMD_HANDSHAKE, NULL, 0);
      if (r307ReceiveResponse(response, &respLen, 700)) {
        if (response[6] == R307_ACK_PACKET && response[9] == 0x00) {
          fingerprintInitialized = true;
          lastErrorMessage = "Fingerprint online";
          return true;
        }
      }
    }
  }
  fingerprintInitialized = false;
  lastErrorMessage = "Fingerprint not found";
  return false;
}

// ============= WiFi INITIALIZATION =============
void initializeWiFi() {
  if (!WiFi.config(local_IP, gateway, subnet, primaryDNS, secondaryDNS)) {
    Serial.println("[WIFI] STA Failed to configure static IP");
  }
  
  WiFi.mode(WIFI_STA);
  WiFi.begin(SSID, PASSWORD);
  int attempts = 0;
  while(WiFi.status() != WL_CONNECTED && attempts < 20) {
    delay(500);
    attempts++;
  }

  if (WiFi.status() == WL_CONNECTED) {
    Serial.print("[WIFI] Connected! Static IP: ");
    Serial.println(WiFi.localIP());
  } else {
    Serial.println("[WIFI] Connection failed, using DHCP fallback if available");
  }
}

// ============= WEB SERVER INITIALIZATION =============
void initializeWebServer() {
  delay(100);
  while (fingerprintSerial.available()) {
    fingerprintSerial.read();
  }
  
  server.on("/", HTTP_GET, handleRoot);
  server.on("/start-enrollment", HTTP_POST, handleStartEnrollment);
  server.on("/start-verification", HTTP_POST, handleStartVerification);
  server.on("/error-feedback", HTTP_POST, handleErrorFeedback);
  server.on("/start-enrollment", HTTP_OPTIONS, []() { addCorsHeaders(); server.send(204); });
  server.on("/start-verification", HTTP_OPTIONS, []() { addCorsHeaders(); server.send(204); });
  server.on("/delete-fingerprint", HTTP_POST, handleDeleteFingerprint);
  server.on("/delete-fingerprint", HTTP_OPTIONS, []() { addCorsHeaders(); server.send(204); });
  server.on("/empty-library", HTTP_POST, handleEmptyLibrary);
  server.on("/empty-library", HTTP_OPTIONS, []() { addCorsHeaders(); server.send(204); });
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
  // Serial.println("[WEB] HTTP server started");
  // Serial.println("[WEB] Available endpoints:");
  // Serial.println("  - GET  /           - System info");
  // Serial.println("  - POST /start-enrollment - Start biometric enrollment");
  // Serial.println("  - POST /stop-enrollment  - Stop enrollment");
  // Serial.println("  - GET  /status     - Get current status");
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
  
  // No lockout - allow new start to override active error beeps
  if (currentState == AUTH_FAILED) {
    isBeeping = false;
    ledcWriteTone(BUZZER_LEDC_CHANNEL, 0);
  }

  if (server.hasArg("id")) {
    enrollmentSlotID = server.arg("id").toInt();
  } else {
    enrollmentSlotID = 0;
  }

  // 1. SET STATE IMMEDIATELY for visual feedback (Blue LED start blinking)
  currentState = ENROLLING;
  enrollmentActive = true;
  currentScan = 0;
  matchedFingerprintID = 0;
  memset(scanCompleted, 0, sizeof(scanCompleted));
  lastErrorMessage = "Ready";
  
  // 2. Perform initialization in background or check if needed
  if (!fingerprintInitialized) {
    fingerprintInitialized = initializeFingerprintModule();
  }
  
  clearR307Buffer();
  if (fingerprintInitialized) {
    r307GenerateImage();
  }

  String response = "{";
  response += "\"status\":\"success\",";
  response += "\"message\":\"Enrollment started for slot " + String(enrollmentSlotID) + "\",";
  response += "\"total_scans\":3,";
  response += "\"current_scan\":1,";
  response += "\"state\":\"enrolling\"";
  response += "}";
  server.send(200, "application/json", response);
}

void handleStartVerification() {
  addCorsHeaders();

  // No lockout - allow new start to override active error beeps
  if (currentState == AUTH_FAILED) {
    isBeeping = false;
    ledcWriteTone(BUZZER_LEDC_CHANNEL, 0);
  }

  clearR307Buffer(); // CLEAR SERIAL BUFFER
  currentState = VERIFYING;
  currentScan = 0;
  enrollmentActive = true;
  matchedFingerprintID = 0;
  lastErrorMessage = "Ready";
  for (int i = 0; i < 3; i++) scanCompleted[i] = false;
  
  String response = "{\"status\":\"success\",\"message\":\"Biometric verification started\",\"state\":\"verifying\"}";
  server.send(200, "application/json", response);
}

void handleDeleteFingerprint() {
  addCorsHeaders();
  if (!server.hasArg("id")) {
    server.send(400, "application/json", "{\"status\":\"error\",\"message\":\"Missing ID\"}");
    return;
  }
  
  int id = server.arg("id").toInt();
  uint8_t data[4] = {(uint8_t)((id >> 8) & 0xFF), (uint8_t)(id & 0xFF), 0x00, 0x01}; // PageID high, PageID low, Num high, Num low (1)
  r307SendCommand(R307_CMD_DELETE, data, 4);
  
  uint8_t response[12];
  uint16_t respLen = 0;
  if (r307ReceiveResponse(response, &respLen, 1000)) {
    if (response[9] == 0x00) {
      server.send(200, "application/json", "{\"status\":\"success\",\"message\":\"Fingerprint deleted\"}");
    } else {
      String msg = "{\"status\":\"error\",\"message\":\"Delete failed (0x" + String(response[9], HEX) + ")\"}";
      server.send(200, "application/json", msg);
    }
  } else {
    server.send(500, "application/json", "{\"status\":\"error\",\"message\":\"Sensor timeout\"}");
  }
}

void handleEmptyLibrary() {
  addCorsHeaders();
  r307SendCommand(R307_CMD_EMPTY, NULL, 0);
  
  uint8_t response[12];
  uint16_t respLen = 0;
  if (r307ReceiveResponse(response, &respLen, 2000)) {
    if (response[9] == 0x00) {
      server.send(200, "application/json", "{\"status\":\"success\",\"message\":\"Library emptied\"}");
    } else {
      String msg = "{\"status\":\"error\",\"message\":\"Empty failed (0x" + String(response[9], HEX) + ")\"}";
      server.send(200, "application/json", msg);
    }
  } else {
    server.send(500, "application/json", "{\"status\":\"error\",\"message\":\"Sensor timeout\"}");
  }
}

void handleErrorFeedback() {
  addCorsHeaders();
  triggerAuthFailed("External request");
  server.send(200, "application/json", "{\"status\":\"success\"}");
}

void triggerAuthFailed(String reason) {
  // IGNORE new triggers if we are already beeping to prevent restarts
  if (isBeeping) {
    return; 
  }

  Serial.printf("\n[SYSTEM] Triggering Auth Failed! Reason: %s\n", reason.c_str());
  isBeeping = true;
  currentState = AUTH_FAILED;
  authFailedResetPending = true;
  enrollmentActive = false;
  detectionStartTime = millis();
  lastErrorMessage = "Auth Failed: " + reason;
  
  // Clear any existing visual/audio states
  setLeds(false, false, false);
  ledcWriteTone(BUZZER_LEDC_CHANNEL, 0);
}

void handleStopEnrollment() {
  addCorsHeaders();
  currentState = STANDBY;
  enrollmentActive = false;
  currentScan = 0; // Reset scan count
  lastErrorMessage = "Ready";

  String response = "{\"status\":\"success\",\"message\":\"Enrollment stopped\",\"state\":\"standby\"}";
  server.send(200, "application/json", response);
}

void handleGetStatus() {
  addCorsHeaders();
  String stateStr;
  switch(currentState) {
    case STANDBY: stateStr = "standby"; break;
    case ENROLLING: stateStr = "enrolling"; break;
    case VERIFYING: stateStr = "verifying"; break;
    case WAIT_REMOVE: stateStr = "wait_remove"; break;
    case FINGERPRINT_DETECTED: stateStr = "detected"; break;
    case AUTH_FAILED: stateStr = "auth_failed"; break;
    default: stateStr = "unknown"; break;
  }
  
  String response = "{";
  response += "\"state\":\"" + stateStr + "\",";
  response += "\"last_error\":\"" + lastErrorMessage + "\",";
  response += "\"fingerprint_initialized\":" + String(fingerprintInitialized ? "true" : "false") + ",";
  response += "\"enrollment_active\":" + String(enrollmentActive ? "true" : "false") + ",";
  response += "\"current_scan\":" + String(currentScan) + ",";
  response += "\"total_scans\":" + String(MAX_SCANS) + ",";
  response += "\"fingerprint_id\":" + String(matchedFingerprintID) + ",";
  response += "\"ip\":\"" + WiFi.localIP().toString() + "\",";
  response += "\"uptime\":" + String(millis()) + ",";
  response += "\"wifi_signal\":" + String(WiFi.RSSI());
  response += "}";
  
  server.send(200, "application/json", response);
}

// ============= STANDBY MODE (Red LED steady) =============
void handleStandbyMode() {
  unsigned long currentTime = millis();
  
  // SLOW BLINK logic (1 second):
  if (currentTime - lastRedBlinkTime >= 500) { // Toggle every 500ms for 1s cycle
    lastRedBlinkTime = currentTime;
    redLedState = !redLedState;
    
    // Standby: Blink Red, keep others OFF
    setLeds(redLedState, false, false);
    
    ledcWriteTone(BUZZER_LEDC_CHANNEL, 0);
    ledcWrite(BUZZER_LEDC_CHANNEL, 0);
  }
}

void handleEnrollingMode() {
  unsigned long currentTime = millis();
  
  // VERY FAST BLINK logic (0.3 second total cycle - 150ms on/off):
  if (currentTime - lastRedBlinkTime >= 150) { 
    lastRedBlinkTime = currentTime;
    redLedState = !redLedState;
    
    // Enrollment/Verification: Blink Blue, keep others OFF
    // CRITICAL: We only force OFF here if we are NOT in a success/remove state
    if (currentState == ENROLLING || currentState == VERIFYING) {
      setLeds(false, false, redLedState);
    } else if (currentState == WAIT_REMOVE) {
      // While waiting for removal, keep Green ON and blink Blue
      setLeds(false, true, redLedState);
    }
  }
}

// ============= DETECTION MODE (Green LED steady for 1 second) =============
void handleDetectionMode() {
  unsigned long currentTime = millis();
  unsigned long elapsedTime = currentTime - detectionStartTime;
  
  // Hold Green LED steady during the 1-second pulse
  setLeds(false, true, false);
  
  // After 1 second: turn off LED, stop buzzer, transition state
  if (elapsedTime >= 1000) {
    setLeds(false, false, false);
    ledcWriteTone(BUZZER_LEDC_CHANNEL, 0); // Ensure buzzer is off
    ledcWrite(BUZZER_LEDC_CHANNEL, 0);
    buzzerPulseActive = false;
    
    // Go to WAIT_REMOVE if more enrollment scans needed, else STANDBY
    if (enrollmentActive && currentScan < MAX_SCANS) {
      currentState = WAIT_REMOVE;
    } else {
      currentState = STANDBY;
    }
  }
}

void handleFailMode() {
  // CRITICAL: Using a blocking loop to guarantee the beeps NEVER stop or stutter
  Serial.println("\n[ERROR-SEQUENCE] ========== STARTING BLOCKING 3-BEEP FEEDBACK ==========");
  
  isBeeping = true;
  authFailedResetPending = false;

  for (int i = 0; i < 3; i++) {
    Serial.printf("[DEBUG] Beep %d Start\n", i + 1);
    
    // Tone ON
    ledcWriteTone(BUZZER_LEDC_CHANNEL, BUZZER_TONE_HZ);
    ledcWrite(BUZZER_LEDC_CHANNEL, 220);
    setLeds(true, false, false);
    delay(300); // 300ms Beep
    
    // Tone OFF
    Serial.printf("[DEBUG] Beep %d End\n", i + 1);
    ledcWriteTone(BUZZER_LEDC_CHANNEL, 0);
    ledcWrite(BUZZER_LEDC_CHANNEL, 0);
    setLeds(false, false, false);
    
    if (i < 2) {
      Serial.println("[DEBUG] Gap Start");
      delay(200); // 200ms Gap (0.2s interval)
    }
  }

  Serial.println("[ERROR-SEQUENCE] ============== SEQUENCE COMPLETE ==============");
  
  // Return to standby
  currentState = STANDBY;
  isBeeping = false;
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
        // Serial.println("\n[CMD] State changed to: STANDBY");
        break;
      case 'e':
      case 'E':
        currentState = ENROLLING;
        lastRedBlinkTime = millis();
        // Serial.println("\n[CMD] State changed to: ENROLLING");
        // Serial.println("[CMD] System is now waiting for fingerprint detection...");
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
// NOTE: No early-return guard here - Green LED MUST always fire on success.
void triggerFingerprintDetection() {
  Serial.println("[SYSTEM] SUCCESS! Showing Green LED feedback.");

  // Set state for visual feedback display
  currentState = FINGERPRINT_DETECTED;
  detectionStartTime = millis();

  // Update scan tracking (only meaningful for enrollment)
  if (enrollmentActive) {
    currentScan++;
    if (currentScan > MAX_SCANS) currentScan = MAX_SCANS;
    int idx = currentScan - 1;
    if (idx >= 0 && idx < MAX_SCANS) scanCompleted[idx] = true;
    Serial.printf("[DEBUG] Enrollment scan %d/%d complete.\n", currentScan, MAX_SCANS);
    if (currentScan >= MAX_SCANS) {
      enrollmentActive = false; // All scans done
      Serial.println("[DEBUG] All scans complete. enrollmentActive = false.");
    }
  }

  // SUCCESS FEEDBACK: Turn on Green LED and Buzzer at the same time
  setLeds(false, true, false);
  ledcWriteTone(BUZZER_LEDC_CHANNEL, BUZZER_TONE_HZ);
  ledcWrite(BUZZER_LEDC_CHANNEL, 200);
  
  buzzerPulseActive = true;
  buzzerPulseStartTime = millis();
  
  Serial.printf("[DEBUG] Success! GREEN LED ON (GPIO %d) + BUZZER ON.\n", GREEN_LED_PIN);
  delay(150);
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
  if ((currentState != ENROLLING && currentState != VERIFYING && currentState != WAIT_REMOVE) || !enrollmentActive) {
    return;
  }
  
  unsigned long currentTime = millis();
  // Poll every 200ms - fast but stable
  if (currentTime - lastImageGenTime < 200) {
    return;
  }
  lastImageGenTime = currentTime;
  
  // 1. Generate Image (Synchronous)
  uint8_t code = r307GenerateImage();
  
  // 2. Handle Wait for Remove state
  if (currentState == WAIT_REMOVE) {
    // Green LED is handled in handleEnrollingMode for this state to allow blinking Blue
    if (code == 0x02) { // No finger on sensor
      currentState = ENROLLING;
      lastErrorMessage = "Place finger on sensor";
    } else {
      lastErrorMessage = "Remove finger...";
    }
    return;
  }

  // 3. Handle Detection
  if (code == 0x00) {
    // Finger detected!
    if (currentState == ENROLLING) {
      // Alternate buffers: scan 0->buf1, scan 1->buf2, scan 2->buf1, etc.
      uint8_t bufferId = (currentScan % 2 == 0) ? 1 : 2;
      uint8_t res = r307Img2Tz(bufferId);
      if (res == 0x00) {
        if (currentScan + 1 >= MAX_SCANS) {
          // FINAL SCAN: build and store template
          Serial.println("[ENROLL] Final scan - running RegModel...");
          if (r307RegModel() == 0x00) {
            if (enrollmentSlotID > 0) {
              if (r307StoreModel(enrollmentSlotID) == 0x00) {
                lastErrorMessage = "Enrolled successfully";
                // NOTE: Do NOT set enrollmentActive=false here.
                // triggerFingerprintDetection handles it internally.
                triggerFingerprintDetection();
              } else {
                triggerAuthFailed("Store failed");
              }
            } else {
              triggerAuthFailed("Invalid slot ID");
            }
          } else {
            triggerAuthFailed("RegModel failed");
          }
        } else {
          // DUPLICATE CHECK: Search existing library before proceeding
          uint16_t duplicateID = 0;
          uint16_t score = 0;
          // Use the SAME buffer we just used for Img2Tz
          if (r307Search(bufferId, &duplicateID, &score) == 0x00) {
            Serial.printf("[ENROLL] Duplicate found! Slot: %d\n", duplicateID);
            matchedFingerprintID = duplicateID; // Store to report back
            triggerAuthFailed("Already registered (ID: " + String(duplicateID) + ")");
            return;
          }

          // INTERMEDIATE SCAN: confirm and wait for remove
          lastErrorMessage = "Scan " + String(currentScan + 1) + " complete. Remove finger.";
          triggerFingerprintDetection(); // increments currentScan and shows green LED
        }
      } else {
        triggerAuthFailed("Img2Tz failed (0x" + String(res, HEX) + ")");
      }
    } else if (currentState == VERIFYING) {
      if (r307Img2Tz(1) == 0x00) {
        uint16_t fingerID = 0;
        uint16_t score = 0;
        if (r307Search(1, &fingerID, &score) == 0x00) {
          matchedFingerprintID = fingerID;
          lastErrorMessage = "Matched ID: " + String(fingerID);
          // Signal done so handleDetectionMode goes to STANDBY, not ENROLLING
          enrollmentActive = false;
          currentScan = MAX_SCANS;
          triggerFingerprintDetection();
        } else {
          triggerAuthFailed("Account not found");
        }
      } else {
        triggerAuthFailed("Scan failed");
      }
    }
  } else if (code == 0x01 || code == 0x02 || code == 0xFF) {
    // 0x01 = packet receive error (sensor still initializing)
    // 0x02 = no finger on sensor (normal idle state)
    // 0xFF = timeout (no response yet - finger not on pad)
    // These are NOT hard failures - just means no finger is detected yet.
    while (fingerprintSerial.available()) fingerprintSerial.read();
    lastErrorMessage = "Place finger on sensor";
  } else {
    // 0x03, 0x06, 0x07 etc. are genuine hardware errors
    triggerAuthFailed("Sensor error (0x" + String(code, HEX) + ")");
  }
}

// ============= R307 FINGERPRINT FUNCTIONS =============

bool r307Handshake() {
  // Serial.println("[R307] 🔄 Attempting module connection...");
  uint8_t password[4] = {0x00, 0x00, 0x00, 0x00};
  r307SendCommand(R307_CMD_VERIFY_PWD, password, 4);
  
  uint8_t response[12];
  uint16_t responseLength = 0;
  
  if (r307ReceiveResponse(response, &responseLength, 3000)) { // Restored to 3000ms for stability
    if (response[6] == R307_ACK_PACKET && response[9] == 0x00) {
      return true;
    }
  }
  
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
  
  // Serial.printf("[R307] Command sent: 0x%02X (length: %d)\n", command, 12 + dataLength);
}

// Receive response from R307 module
bool r307ReceiveResponse(uint8_t* response, uint16_t* responseLength, uint32_t timeout) {
  uint32_t startTime = millis();
  int state = 0; // 0: Hunting for 0xEF, 1: Hunting for 0x01
  
  while (millis() - startTime < timeout) {
    if (fingerprintSerial.available() > 0) {
      uint8_t b = fingerprintSerial.read();
      
      if (state == 0) {
        if (b == R307_START_CODE_1) state = 1;
      } 
      else if (state == 1) {
        if (b == R307_START_CODE_2) {
          // Found header!
          response[0] = R307_START_CODE_1;
          response[1] = R307_START_CODE_2;
          
          // Now read the rest of the fixed header (Address + ID + Length = 7 bytes)
          uint32_t waitStart = millis();
          int headerIndex = 2;
          while (headerIndex < 9 && (millis() - waitStart < 100)) {
            if (fingerprintSerial.available()) {
              response[headerIndex++] = fingerprintSerial.read();
            }
          }
          
          if (headerIndex < 9) return false; // Timeout
          
          uint16_t packetLength = (response[7] << 8) | response[8];
          if (packetLength > 256) return false; // Invalid length
          
          // Read data + checksum
          int dataRead = 0;
          waitStart = millis();
          while (dataRead < packetLength && (millis() - waitStart < 500)) {
            if (fingerprintSerial.available()) {
              response[9 + dataRead++] = fingerprintSerial.read();
            }
          }
          
          if (dataRead < packetLength) return false;
          
          *responseLength = 9 + packetLength;
          return true;
        } else {
          state = 0; // Reset
        }
      }
    }
    yield();
  }
  return false;
}

// Generate fingerprint image (Synchronous for perfect detection)
uint8_t r307GenerateImage() {
  // Clear any noise before sending command
  while(fingerprintSerial.available()) fingerprintSerial.read();
  
  r307SendCommand(R307_CMD_GEN_IMG, NULL, 0);
  
  uint8_t response[12];
  uint16_t respLen = 0;
  // Wait up to 500ms for the sensor to finish capturing the image
  if (r307ReceiveResponse(response, &respLen, 500)) {
    return response[9];
  }
  return 0xFF; // Timeout
}

uint8_t r307Img2Tz(uint8_t slot) {
  uint8_t data[1] = {slot};
  r307SendCommand(R307_CMD_IMG2TZ, data, 1);
  uint8_t response[12];
  uint16_t respLen = 0;
  if (r307ReceiveResponse(response, &respLen, 1000)) {
    return response[9];
  }
  return 0xFF;
}

uint8_t r307RegModel() {
  r307SendCommand(R307_CMD_REG_MODEL, NULL, 0);
  uint8_t response[12];
  uint16_t respLen = 0;
  if (r307ReceiveResponse(response, &respLen, 1000)) {
    return response[9];
  }
  return 0xFF;
}

uint8_t r307StoreModel(uint16_t id) {
  uint8_t data[3] = {0x01, (uint8_t)((id >> 8) & 0xFF), (uint8_t)(id & 0xFF)};
  r307SendCommand(R307_CMD_STORE, data, 3);
  uint8_t response[12];
  uint16_t respLen = 0;
  if (r307ReceiveResponse(response, &respLen, 1000)) {
    return response[9];
  }
  return 0xFF;
}

uint8_t r307Search(uint8_t bufferId, uint16_t* fingerID, uint16_t* score) {
  // data[0] is the buffer ID (0x01 or 0x02)
  uint8_t data[5] = {bufferId, 0x00, 0x00, 0x03, 0xE8}; // BufferId, Start 0, Num 1000
  r307SendCommand(R307_CMD_SEARCH, data, 5);
  uint8_t response[16];
  uint16_t respLen = 0;
  if (r307ReceiveResponse(response, &respLen, 2000)) {
    if (response[9] == 0x00) {
      *fingerID = (response[10] << 8) | response[11];
      *score = (response[12] << 8) | response[13];
    }
    return response[9];
  }
  return 0xFF;
}

// ============= SYSTEM STATUS PRINT =============
void printSystemStatus() {
  // Serial.println("\n================================");
  // Serial.println("SYSTEM STATUS");
  // Serial.println("================================");
  // Serial.printf("Current State: ");
  
  switch(currentState) {
    case STANDBY:
      // Serial.println("STANDBY (Red LED slow blink - 1 second)");
      break;
    case ENROLLING:
      // Serial.println("ENROLLING (Red LED fast blink - waiting for fingerprint)");
      break;
    case FINGERPRINT_DETECTED:
      // Serial.println("FINGERPRINT_DETECTED (Green LED + Buzzer pulsing)");
      break;
  }
  
  // Serial.println("\nAVAILABLE COMMANDS:");
  // Serial.println("  'S' - Change to STANDBY mode");
  // Serial.println("  'E' - Change to ENROLLING mode (simulate start button)");
  // Serial.println("  'D' - Simulate fingerprint DETECTION");
  // Serial.println("  '?' - Print this status\n");
  // Serial.println("================================\n");
}
