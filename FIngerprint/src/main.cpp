#include <Arduino.h>
#include <HardwareSerial.h>
#include <WiFi.h>
#include <ESPmDNS.h>
#include <WebServer.h>
#include <HTTPClient.h>
#include <Wire.h>
#include <LiquidCrystal_I2C.h>
#include <time.h>
#include "soc/soc.h"
#include "soc/rtc_cntl_reg.h"

// ============= WiFi CONFIG =============
// The ESP32 connects to the Orange Pi's dedicated private hotspot.
// The Orange Pi runs hostapd and is ALWAYS at 10.42.0.1 on this network.
// No WiFiManager portal, no dynamic IP guessing — plug and play.
// Residents access the web app via the Orange Pi's LAN (ethernet) interface separately.
#define WIFI_SSID     "Barangay_System_WiFi"
#define WIFI_PASSWORD "barangay123"
#define ORANGE_PI_IP  "10.42.0.1"
#define DJANGO_PORT   8001

// ============= HTTP SERVER CONFIG =============
WebServer server(80);

// ============= PIN DEFINITIONS =============
#define RED_LED_PIN 18          // Label D18
#define GREEN_LED_PIN 27        // MOVED FROM 19 TO 27 TO AVOID CONFLICTS
#define BLUE_LED_PIN 5          // Label D5
#define BUZZER_PIN 4            // MOVED BACK TO PIN 4 AS REQUESTED
#define FINGERPRINT_RX_PIN 22   // GPIO22 (RX2) <- Sensor TX (Green)
#define FINGERPRINT_TX_PIN 23   // GPIO23 (TX2) -> Sensor RX (White)
#define LCD_SDA_PIN 21
#define LCD_SCL_PIN 19          // MOVED TO 19 TO AVOID CONFLICT WITH FINGERPRINT ON 22
#define BUTTON_IN_PIN 32        // Hardware button for TIME IN
#define BUTTON_OUT_PIN 33       // Hardware button for TIME OUT

// ============= SYSTEM STATES =============
enum SystemState {
  STANDBY,      // Module idle, blue LED blinks slowly (1 second)
  ENROLLING,    // Waiting for fingerprint, blue LED blinks fast
  VERIFYING,    // Waiting for login fingerprint, blue LED blinks fast
  WAIT_REMOVE,  // Success! Wait for finger to be removed (Green ON + Blue blinking)
  FINGERPRINT_DETECTED,  // Fingerprint detected, green LED + buzzer sync
  AUTH_FAILED          // Error feedback (Red LED + 3 beeps)
};

// ============= LCD CONFIG =============
// Both common I2C backpack addresses — auto-detected at boot.
// If your LCD is blank/garbled, check Serial Monitor for [LCD] address message.
LiquidCrystal_I2C _lcd_27(0x27, 16, 2);
LiquidCrystal_I2C _lcd_3F(0x3F, 16, 2);
LiquidCrystal_I2C* _lcdPtr = &_lcd_27; // Will be set to correct address at boot
#define lcd (*_lcdPtr)                   // All lcd.xxx() calls use this transparently
unsigned long lastLcdUpdate = 0;
unsigned long lastLCDReinitTime = 0;  // Watchdog: periodic reinit to self-heal corruption
const char* ntpServer = "pool.ntp.org";
const long gmtOffset_sec = 28800; // PHT (UTC+8)
const int daylightOffset_sec = 0;

// ============= ATTENDANCE CONFIG =============
String attendanceMode = "none"; // "in", "out", or "none"
unsigned long lastButtonPress = 0;
bool buttonBootGuardDone = false; // Prevents ghost triggers on first boot
const int debounceDelay = 600;   // Increased from 300ms — reduces noise false-triggers

// ============= TIMING CONSTANTS =============
#define STANDBY_BLINK_INTERVAL 1000      // 1 second for standby (total cycle)
#define ENROLLING_BLINK_INTERVAL 250     // 250ms for fast blinking (total cycle)
#define DETECTION_PULSE_INTERVAL 300     // 300ms for green LED + buzzer sync
#define DETECTION_PULSE_DURATION 1500    // Total time for detection pulse (1.5 seconds)
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
unsigned long lastLCDUpdateTime = 0;
String lastLCDLine1 = "";
String lastLCDLine2 = "";
bool authFailedResetPending = false; // Flag to reset the error beeper
bool isBeeping = false; // Hardware-level lockout to prevent beep restarts

// ============= FINGERPRINT DATA =============
int enrollmentSlotID = 0;
/** Matched library page from last verify/enroll; -1 = none pending for /status JSON. */
int matchedFingerprintID = -1;
/** Template library size from ReadSysPara (AS608 layout); 0 = not read yet. */
uint16_t r307FingerprintCapacity = 0;
/** If >0, VERIFYING Search() checks at most this many pages from index 0 (faster no-match). Set from POST /start-verification max_page. */
uint16_t verifySearchPageCount = 0;
/** After AUTH_FAILED beeps during login verify, return to WAIT_REMOVE→VERIFYING instead of STANDBY. */
bool resumeVerifyingAfterAuthFailBeeps = false;

// ============= ENROLLMENT SYSTEM =============
#define MAX_SCANS 3
int currentScan = 0;
bool enrollmentActive = false;
/** After WAIT_REMOVE (finger lifted), return to this state (ENROLLING vs VERIFYING). */
SystemState resumeStateAfterWaitRemove = ENROLLING;
uint8_t fingerprintTemplates[MAX_SCANS][512]; // Store templates for 3 scans
bool scanCompleted[MAX_SCANS] = {false, false, false};

// ============= ORANGE PI SERVER CONFIG =============
// The Orange Pi is always at 10.42.0.1 on the Barangay_System_WiFi hotspot.
// This IP never changes — no mDNS lookup or DHCP guessing needed.
IPAddress orangePiIP(10, 42, 0, 1);             // FIXED: Orange Pi hotspot IP (permanent)
int mdnsFailCount = 0;                          // Reset when Django contacts us
IPAddress lastAnnouncedOrangePiIP(0,0,0,0);
IPAddress lastAnnouncedLocalIP(0,0,0,0);
unsigned long lastAnnounceAttemptTime = 0;

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
void handleGetStatus();
void handleStopEnrollment();
void handleErrorFeedback();
void updateLCD();
void updateSystemState();
void handleStandbyMode();
void handleEnrollingMode();
void handleDetectionMode();
void handleFailMode();
void detectFingerprint();
void clearR307Buffer();
void addCorsHeaders();
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
uint8_t r307StoreModelFromBuffer(uint8_t charBuffer, uint16_t pageId);
uint8_t r307DeletePage(uint16_t pageId);
uint8_t r307Search(uint8_t bufferId, uint16_t* fingerID, uint16_t* score, uint16_t maxPagesOverride = 0);
bool r307RefreshFingerprintCapacity();
void triggerAuthFailed(const String& reason, bool resumeVerifyingSessionAfterBeeps = false);
void printSystemStatus();
void setLeds(bool red, bool green, bool blue);
void resolveOrangePiIP();
void announceToServer();
void lcdSafeInit();
void lcdSafePrint(const String& line1, const String& line2);

// ============= SETUP =============
void setup() {
  WRITE_PERI_REG(RTC_CNTL_BROWN_OUT_REG, 0); // Disable brownout detector to prevent reboot loop on Wi-Fi initialization
  Serial.begin(115200);
  initializeHardware();
  initializeWiFi();
  digitalWrite(BLUE_LED_PIN, HIGH);
  fingerprintInitialized = initializeFingerprintModule();
  initializeWebServer();

  // Configure NTP
  configTime(gmtOffset_sec, daylightOffset_sec, ntpServer);

  // Safe reinit after all startup noise (WiFi, fingerprint) has settled
  lcdSafeInit();
  lcdSafePrint("System Online", "Ready...");
}

// ============= MAIN LOOP =============
void loop() {
  server.handleClient();
  updateSystemState();
  
  // ============= WiFi WATCHDOG =============
  // Runs every 5 seconds. Reconnects to the barangay hotspot if the link drops.
  // Also re-announces our IP to Django after a reconnect so heartbeat stays fresh.
  {
    static unsigned long lastWiFiCheckTime = 0;
    static int wifiRetryCount = 0;
    unsigned long wifiNow = millis();
    if (wifiNow - lastWiFiCheckTime >= 5000) {
      lastWiFiCheckTime = wifiNow;
      if (WiFi.status() != WL_CONNECTED) {
        wifiRetryCount++;
        lcdSafePrint("Hotspot Lost!", "Retry: " + String(wifiRetryCount));
        Serial.printf("[WIFI] Reconnecting to %s (attempt %d)...\r\n", WIFI_SSID, wifiRetryCount);
        WiFi.disconnect();
        delay(100);
        WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
      } else {
        wifiRetryCount = 0;
        // Re-announce to Django if our assigned IP changed (e.g. fresh reconnect)
        if (currentState == STANDBY &&
            (WiFi.localIP() != lastAnnouncedLocalIP || orangePiIP != lastAnnouncedOrangePiIP)) {
          if (wifiNow - lastAnnounceAttemptTime >= 10000) {
            lastAnnounceAttemptTime = wifiNow;
            announceToServer();
          }
        }
      }
    }
  }
  
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
  
  updateLCD();
  detectFingerprint();

  // Serve HTTP again after sensor work so /status polls do not time out while scanning
  server.handleClient();
  
  // Do not flush UART during enrollment wait-remove — avoids interfering with the module
  if (currentState != ENROLLING && currentState != VERIFYING && currentState != WAIT_REMOVE) {
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

  // Setup Buzzer (ESP32 LEDC)
  ledcSetup(BUZZER_LEDC_CHANNEL, 4000, 8); // 4kHz, 8-bit resolution
  ledcAttachPin(BUZZER_PIN, BUZZER_LEDC_CHANNEL);

  // Initialize Hardware Buttons
  pinMode(BUTTON_IN_PIN, INPUT_PULLUP);
  pinMode(BUTTON_OUT_PIN, INPUT_PULLUP);

  // ---- Step 1: Hardware I2C Bus Recovery ----
  // Toggle SCL 9 times to release any slave that held SDA LOW after a power glitch.
  // Must happen BEFORE Wire.begin().
  pinMode(LCD_SDA_PIN, OUTPUT);
  pinMode(LCD_SCL_PIN, OUTPUT);
  digitalWrite(LCD_SDA_PIN, HIGH);
  for (int i = 0; i < 9; i++) {
    digitalWrite(LCD_SCL_PIN, LOW);  delayMicroseconds(10);
    digitalWrite(LCD_SCL_PIN, HIGH); delayMicroseconds(10);
  }
  // Issue I2C STOP: SDA LOW->HIGH while SCL HIGH
  digitalWrite(LCD_SDA_PIN, LOW);  delayMicroseconds(10);
  digitalWrite(LCD_SCL_PIN, HIGH); delayMicroseconds(10);
  digitalWrite(LCD_SDA_PIN, HIGH); delayMicroseconds(10);
  // Return pins to open-drain for Wire library
  pinMode(LCD_SCL_PIN, INPUT_PULLUP);
  pinMode(LCD_SDA_PIN, INPUT_PULLUP);
  delay(50); // Let VCC/GND settle

  // ---- Step 2: Start I2C at ultra-low speed ----
  // 25 kHz is much more resilient to long wires and RF noise than 100 kHz.
  Wire.begin(LCD_SDA_PIN, LCD_SCL_PIN);
  Wire.setClock(25000);
  delay(100); // HD44780 power-on init requires ≥40ms after Vcc

  // ---- Step 3: Auto-detect I2C address (0x27 or 0x3F) ----
  // Some LCD backpacks use 0x3F instead of 0x27. We scan both and use whichever responds.
  Wire.beginTransmission(0x27);
  if (Wire.endTransmission() == 0) {
    _lcdPtr = &_lcd_27;
    Serial.println("[LCD] Detected I2C address: 0x27");
  } else {
    Wire.beginTransmission(0x3F);
    if (Wire.endTransmission() == 0) {
      _lcdPtr = &_lcd_3F;
      Serial.println("[LCD] Detected I2C address: 0x3F");
    } else {
      _lcdPtr = &_lcd_27; // Fallback
      Serial.println("[LCD] WARNING: No LCD found on 0x27 or 0x3F — check wiring!");
    }
  }

  // ---- Step 4: Full LCD init (no Wire.end here, ever) ----
  lcdSafeInit();
  lcdSafePrint("System Booting", "Please wait...");

  // Set all LEDs OFF
  setLeds(false, false, false);

  // HARDWARE TEST: Cycle all LEDs and beep to verify wiring
  Serial.println("[BOOT] Starting Hardware Self-Test...");
  setLeds(true, false, false);  delay(300);
  setLeds(false, true, false);  delay(300);
  setLeds(false, false, true);  delay(300);
  setLeds(false, true, false);
  ledcWriteTone(BUZZER_LEDC_CHANNEL, BUZZER_TONE_HZ);
  ledcWrite(BUZZER_LEDC_CHANNEL, 150);
  delay(200);
  ledcWriteTone(BUZZER_LEDC_CHANNEL, 0);
  setLeds(false, false, false);
  Serial.println("[BOOT] Hardware test complete.");
  delay(100);
}

// Set this to 'true' if you are using a Common Anode RGB LED (where LOW turns the LED ON)
// Set to 'false' if you are using a Common Cathode RGB LED (where HIGH turns the LED ON)
const bool LED_ACTIVE_LOW = true; 

// ============= LED CONTROL UTILITY =============
void setLeds(bool red, bool green, bool blue) {
  if (LED_ACTIVE_LOW) {
    digitalWrite(RED_LED_PIN, red ? LOW : HIGH);
    digitalWrite(GREEN_LED_PIN, green ? LOW : HIGH);
    digitalWrite(BLUE_LED_PIN, blue ? LOW : HIGH);
  } else {
    digitalWrite(RED_LED_PIN, red ? HIGH : LOW);
    digitalWrite(GREEN_LED_PIN, green ? HIGH : LOW);
    digitalWrite(BLUE_LED_PIN, blue ? HIGH : LOW);
  }
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
          r307RefreshFingerprintCapacity();
          return true;
        }
      }
      r307SendCommand(R307_CMD_HANDSHAKE, NULL, 0);
      if (r307ReceiveResponse(response, &respLen, 700)) {
        if (response[6] == R307_ACK_PACKET && response[9] == 0x00) {
          fingerprintInitialized = true;
          lastErrorMessage = "Fingerprint online";
          r307RefreshFingerprintCapacity();
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
// Hardcoded to connect to the Orange Pi's dedicated hotspot.
// The Orange Pi is ALWAYS at 10.42.0.1 on this private network — no portal, no guessing.
void initializeWiFi() {
  lcdSafePrint("Connecting WiFi", WIFI_SSID);

  WiFi.mode(WIFI_STA);
  WiFi.setTxPower(WIFI_POWER_11dBm); // Reduce TX power to avoid brownout
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);

  int attempts = 0;
  while (WiFi.status() != WL_CONNECTED) {
    delay(1000);
    attempts++;
    Serial.printf("[WIFI] Connecting to %s... attempt %d\r\n", WIFI_SSID, attempts);
    lcdSafePrint("Connecting WiFi", "Attempt: " + String(attempts));

    // After 30 seconds, restart to recover from any hardware/startup fault.
    // The WiFi watchdog in loop() will handle reconnects after a clean boot.
    if (attempts >= 30) {
      Serial.println("[WIFI] Hotspot not found. Ensure Orange Pi is running. Restarting...");
      lcdSafePrint("Hotspot Missing!", "Restarting...");
      delay(3000);
      ESP.restart();
    }
  }

  // CRITICAL: WiFi startup generates heavy RF noise on I2C bus.
  // Always do a full safe reinit before writing to LCD after WiFi connects.
  lcdSafeInit();

  Serial.print("[WIFI] Connected to ");
  Serial.print(WIFI_SSID);
  Serial.print(", IP: ");
  Serial.println(WiFi.localIP());
  Serial.println("[WIFI] Orange Pi server: http://" ORANGE_PI_IP ":" + String(DJANGO_PORT) + " (fixed)");

  lcdSafePrint("WiFi Connected!", WiFi.localIP().toString());
  delay(2000);

  // Start mDNS so Django can discover this ESP32 as http://esp32-fingerprint.local
  if (MDNS.begin("esp32-fingerprint")) {
    Serial.println("[MDNS] ESP32 mDNS responder started: http://esp32-fingerprint.local");
    MDNS.addService("http", "tcp", 80);
  } else {
    Serial.println("[MDNS] Error starting mDNS responder.");
  }

  // Orange Pi is always at 10.42.0.1 — announce our IP immediately on boot
  lastAnnounceAttemptTime = millis();
  announceToServer();
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

  // Dynamically learn the Orange Pi IP address from incoming Django requests
  if (server.client()) {
    IPAddress clientIP = server.client().remoteIP();
    if (clientIP.toString() != "0.0.0.0" && clientIP.toString() != "127.0.0.1") {
      orangePiIP = clientIP;
      mdnsFailCount = 0; // Reset mDNS fail counter since we established communication
    }
  }
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

  if (!server.hasArg("id")) {
    server.send(400, "application/json",
      "{\"status\":\"error\",\"message\":\"Missing id (page index). Start enrollment from the web app.\"}");
    return;
  }
  enrollmentSlotID = server.arg("id").toInt();

  if (!fingerprintInitialized) {
    fingerprintInitialized = initializeFingerprintModule();
  }
  if (fingerprintInitialized && r307FingerprintCapacity == 0) {
    r307RefreshFingerprintCapacity();
  }

  // AS608 page index is 0 .. capacity-1
  if (enrollmentSlotID < 0) {
    server.send(400, "application/json",
      "{\"status\":\"error\",\"message\":\"Invalid enrollment page index. Re-open enrollment from the web app.\"}");
    return;
  }
  if (r307FingerprintCapacity > 0 && enrollmentSlotID >= (int)r307FingerprintCapacity) {
    String body = "{\"status\":\"error\",\"message\":\"Page ";
    body += String(enrollmentSlotID);
    body += " is out of range for this sensor (0-";
    body += String((unsigned)(r307FingerprintCapacity - 1));
    body += "). Refresh the enrollment page.\"}";
    server.send(400, "application/json", body);
    return;
  }

  // 1. SET STATE IMMEDIATELY for visual feedback (Blue LED start blinking)
  currentState = ENROLLING;
  enrollmentActive = true;
  currentScan = 0;
  matchedFingerprintID = -1;
  memset(scanCompleted, 0, sizeof(scanCompleted));
  lastErrorMessage = "Ready";
  
  clearR307Buffer();
  if (fingerprintInitialized) {
    // Clear target page so re-enroll after "remove" in the app is not blocked by stale flash
    r307DeletePage((uint16_t)enrollmentSlotID);
    delay(80);
    r307GenerateImage();
  }

  String response = "{";
  response += "\"status\":\"success\",";
  response += "\"message\":\"Enrollment started for slot " + String(enrollmentSlotID) + "\",";
  response += "\"total_scans\":3,";
  response += "\"current_scan\":1,";
  response += "\"state\":\"enrolling\",";
  response += "\"max_fingerprint_slots\":" + String(r307FingerprintCapacity);
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

  verifySearchPageCount = 0;
  if (server.hasArg("max_page")) {
    int mp = server.arg("max_page").toInt();
    if (mp >= 0) {
      long pages = (long)mp + 1 + 8;
      if (pages < 16) {
        pages = 16;
      }
      if (pages > 1000) {
        pages = 1000;
      }
      verifySearchPageCount = (uint16_t)pages;
    }
  }
  if (fingerprintInitialized && r307FingerprintCapacity > 0 && verifySearchPageCount > r307FingerprintCapacity) {
    verifySearchPageCount = r307FingerprintCapacity;
  }

  String requestMode = "none";
  if (server.hasArg("mode")) {
    requestMode = server.arg("mode");
  }

  // --- NEW: Dynamic Server IP Registration ---
  // If Django passes its IP, learn it instantly instead of waiting for mDNS
  if (server.hasArg("server_ip")) {
    String sip = server.arg("server_ip");
    IPAddress newIP;
    if (newIP.fromString(sip)) {
      orangePiIP = newIP;
      Serial.println("[SYNC] Learned Django Server IP: " + orangePiIP.toString());
    }
  }

  if (currentState == VERIFYING) {
    // Already in verifying mode (triggered by hardware button or active session)
    // Don't reset if we already have a match waiting
    if (matchedFingerprintID != -1) {
      server.send(200, "application/json", "{\"status\":\"success\",\"message\":\"Already verified\",\"state\":\"verifying\"}");
      return;
    }
    // Just refresh the message and proceed
    lastErrorMessage = "Ready";
    
    // CRITICAL FIX: Always update attendance mode, even if already verifying!
    attendanceMode = requestMode;
  } else {
    // Double-clear UART buffer: flush any stale packets from previous session
    clearR307Buffer();
    delay(30);
    clearR307Buffer();
    currentState = VERIFYING;
    currentScan = 0;
    enrollmentActive = true;
    matchedFingerprintID = -1;
    lastImageGenTime = 0; // Reset poll timer so first scan fires immediately (not after 150ms)
    
    // Only update attendanceMode if it was provided, otherwise default to "none" (login)
    attendanceMode = requestMode;
    
    resumeStateAfterWaitRemove = ENROLLING;
    lastErrorMessage = "Ready";
    for (int i = 0; i < 3; i++) scanCompleted[i] = false;
  }
  
  String response = "{\"status\":\"success\",\"message\":\"Biometric verification started\",\"state\":\"verifying\"}";
  if (verifySearchPageCount > 0) {
    response = "{\"status\":\"success\",\"message\":\"Biometric verification started\",\"state\":\"verifying\","
               "\"search_pages\":" + String(verifySearchPageCount) + "}";
  }
  server.send(200, "application/json", response);
}

void handleDeleteFingerprint() {
  addCorsHeaders();
  if (!server.hasArg("id")) {
    server.send(400, "application/json", "{\"status\":\"error\",\"message\":\"Missing ID\"}");
    return;
  }

  if (!fingerprintInitialized) {
    fingerprintInitialized = initializeFingerprintModule();
  }
  if (!fingerprintInitialized) {
    server.send(503, "application/json",
      "{\"status\":\"error\",\"message\":\"Fingerprint sensor not connected\"}");
    return;
  }

  int id = server.arg("id").toInt();
  clearR307Buffer();
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
  if (!fingerprintInitialized) {
    fingerprintInitialized = initializeFingerprintModule();
  }
  if (!fingerprintInitialized) {
    server.send(503, "application/json",
      "{\"status\":\"error\",\"message\":\"Fingerprint sensor not connected or not responding\"}");
    return;
  }

  clearR307Buffer();
  r307SendCommand(R307_CMD_EMPTY, NULL, 0);

  uint8_t response[12];
  uint16_t respLen = 0;
  if (r307ReceiveResponse(response, &respLen, 8000)) {
    if (response[9] == 0x00) {
      currentState = STANDBY;
      enrollmentActive = false;
      currentScan = 0;
      matchedFingerprintID = -1;
      isBeeping = false;
      ledcWriteTone(BUZZER_LEDC_CHANNEL, 0);
      lastErrorMessage = "Sensor library cleared";
      r307RefreshFingerprintCapacity();
      Serial.println("[R307] Library emptied (all templates deleted on module)");
      delay(1000); // Flash erase settle before next enroll/store (reduces 0x18 FLASHERR)
      server.send(200, "application/json",
        "{\"status\":\"success\",\"message\":\"All fingerprints deleted from the sensor module\"}");
    } else {
      String msg = "{\"status\":\"error\",\"message\":\"Empty library failed (0x" + String(response[9], HEX) + ")\"}";
      server.send(502, "application/json", msg);
    }
  } else {
    server.send(504, "application/json", "{\"status\":\"error\",\"message\":\"Sensor timeout during empty library\"}");
  }
}

void handleErrorFeedback() {
  addCorsHeaders();
  String reason = "External request";
  if (server.hasArg("reason")) {
    reason = server.arg("reason");
  }
  matchedFingerprintID = -1;
  attendanceMode = "none";
  triggerAuthFailed(reason);
  server.send(200, "application/json", "{\"status\":\"success\"}");
}

void triggerAuthFailed(const String& reason, bool resumeVerifyingSessionAfterBeeps) {
  // IGNORE new triggers if we are already beeping to prevent restarts
  if (isBeeping) {
    return; 
  }

  resumeVerifyingAfterAuthFailBeeps = resumeVerifyingSessionAfterBeeps;
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

  // Force LCD update to show the failure reason before blocking beeps start
  lastLCDUpdateTime = 0; 
  updateLCD();
}

void handleStopEnrollment() {
  addCorsHeaders();
  if (isBeeping || currentState == AUTH_FAILED) {
    server.send(200, "application/json", "{\"status\":\"ignored\",\"message\":\"Beeping in progress\",\"state\":\"auth_failed\"}");
    return;
  }
  currentState = STANDBY;
  enrollmentActive = false;
  currentScan = 0; // Reset scan count
  resumeStateAfterWaitRemove = ENROLLING;
  matchedFingerprintID = -1;
  attendanceMode = "none";
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

  // Retrieve current timeinfo from internal RTC (NTP synchronized)
  time_t epoch = 0;
  time(&epoch);
  struct tm timeinfo;
  String devTime = "";
  String devDate = "";
  if (epoch > 1000000000 && getLocalTime(&timeinfo, 50)) {
    char tBuf[20];
    char dBuf[20];
    strftime(tBuf, sizeof(tBuf), "%H:%M:%S", &timeinfo);
    strftime(dBuf, sizeof(dBuf), "%Y-%m-%d", &timeinfo);
    devTime = String(tBuf);
    devDate = String(dBuf);
  }
  
  String response = "{";
  response += "\"state\":\"" + stateStr + "\",";
  response += "\"last_error\":\"" + lastErrorMessage + "\",";
  response += "\"max_fingerprint_slots\":" + String(r307FingerprintCapacity) + ",";
  response += "\"fingerprint_initialized\":" + String(fingerprintInitialized ? "true" : "false") + ",";
  response += "\"enrollment_active\":" + String(enrollmentActive ? "true" : "false") + ",";
  response += "\"current_scan\":" + String(currentScan) + ",";
  response += "\"total_scans\":" + String(MAX_SCANS) + ",";
  
  if (matchedFingerprintID >= 0) {
    response += "\"fingerprint_id\":" + String(matchedFingerprintID) + ",";
    response += "\"attendance_mode\":\"" + attendanceMode + "\",";
    // Do not consume here to prevent race conditions if Django request drops
  }
  
  response += "\"device_time\":\"" + devTime + "\",";
  response += "\"device_date\":\"" + devDate + "\",";
  response += "\"ip\":\"" + WiFi.localIP().toString() + "\",";
  response += "\"uptime\":" + String(millis()) + ",";
  response += "\"wifi_signal\":" + String(WiFi.RSSI());
  response += "}";
  
  server.send(200, "application/json", response);
}

// ============= STANDBY MODE (Blue LED slow blink) =============
void handleStandbyMode() {
  unsigned long currentTime = millis();
  
  // Clear stale matched ID after 10 seconds if Django fails to poll
  if (matchedFingerprintID != -1 && (currentTime - detectionStartTime > 10000)) {
    matchedFingerprintID = -1;
    attendanceMode = "none";
    lastErrorMessage = "Ready";
    lastLCDUpdateTime = 0; // Force LCD update
  }

  // SLOW BLINK logic (1 second):
  if (currentTime - lastRedBlinkTime >= 500) { // Toggle every 500ms for 1s cycle
    lastRedBlinkTime = currentTime;
    redLedState = !redLedState;
    
    // Standby: Blink Blue slowly, keep others OFF (matches slow blue standby comment)
    setLeds(false, false, redLedState);
    
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
  
  // After 1.5 seconds: turn off LED, stop buzzer, transition state
  if (elapsedTime >= 1500) {
    setLeds(false, false, false);
    ledcWriteTone(BUZZER_LEDC_CHANNEL, 0); // Ensure buzzer is off
    ledcWrite(BUZZER_LEDC_CHANNEL, 0);
    buzzerPulseActive = false;
    
    // Go to WAIT_REMOVE if more enrollment scans needed, else STANDBY
    if (enrollmentActive && currentScan < MAX_SCANS) {
      resumeStateAfterWaitRemove = ENROLLING;
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
  
  if (resumeVerifyingAfterAuthFailBeeps) {
    resumeVerifyingAfterAuthFailBeeps = false;
    enrollmentActive = true;
    currentScan = 0;
    matchedFingerprintID = -1;
    for (int i = 0; i < MAX_SCANS; i++) {
      scanCompleted[i] = false;
    }
    resumeStateAfterWaitRemove = VERIFYING;
    currentState = WAIT_REMOVE;
    lastErrorMessage = "Not registered — remove finger, then try again";
  } else {
    currentState = STANDBY;
  }
  isBeeping = false;
}

// ============= UPDATE SYSTEM STATE =============
void updateSystemState() {
  // Boot guard: skip button checks for the first 2 seconds after power-on
  // This prevents floating/noisy GPIO from immediately triggering TIME IN on startup
  if (!buttonBootGuardDone) {
    if (millis() < 2000) return;
    buttonBootGuardDone = true;
    lastButtonPress = millis(); // Arm debounce from NOW, not from 0
  }

  // Check Hardware Buttons (TIME IN / TIME OUT)
  if (millis() - lastButtonPress > debounceDelay) {
    bool inPressed  = (digitalRead(BUTTON_IN_PIN)  == LOW);
    bool outPressed = (digitalRead(BUTTON_OUT_PIN) == LOW);

    // Double-sample confirmation: re-read after 10ms to filter noise/glitches
    if (inPressed || outPressed) {
      delay(10);
      inPressed  = (digitalRead(BUTTON_IN_PIN)  == LOW);
      outPressed = (digitalRead(BUTTON_OUT_PIN) == LOW);
    }

    if (inPressed) {
      lastButtonPress = millis();
      attendanceMode = "in";
      clearR307Buffer();
      delay(30);
      clearR307Buffer();
      currentState = VERIFYING;
      enrollmentActive = true;
      currentScan = 0;
      matchedFingerprintID = -1;
      lastImageGenTime = 0; // Reset poll timer so first scan fires immediately
      lastErrorMessage = "TIME IN selected";
      Serial.println("[BUTTON] TIME IN pressed");
      // --- Buzzer: two short beeps ---
      for (int i = 0; i < 2; i++) {
        ledcWriteTone(BUZZER_LEDC_CHANNEL, 3000);
        ledcWrite(BUZZER_LEDC_CHANNEL, 160);
        delay(80);
        ledcWriteTone(BUZZER_LEDC_CHANNEL, 0);
        if (i < 1) delay(80);
      }
    } else if (outPressed) {
      lastButtonPress = millis();
      attendanceMode = "out";
      clearR307Buffer();
      delay(30);
      clearR307Buffer();
      currentState = VERIFYING;
      enrollmentActive = true;
      currentScan = 0;
      matchedFingerprintID = -1;
      lastImageGenTime = 0; // Reset poll timer so first scan fires immediately
      lastErrorMessage = "TIME OUT selected";
      Serial.println("[BUTTON] TIME OUT pressed");
      // --- Buzzer: two short beeps ---
      for (int i = 0; i < 2; i++) {
        ledcWriteTone(BUZZER_LEDC_CHANNEL, 3000);
        ledcWrite(BUZZER_LEDC_CHANNEL, 160);
        delay(80);
        ledcWriteTone(BUZZER_LEDC_CHANNEL, 0);
        if (i < 1) delay(80);
      }
    }
  }

  // 10-second expiration for hardware buttons if no fingerprint is placed
  if (currentState == VERIFYING && attendanceMode != "none") {
    if (millis() - lastButtonPress > 10000) {
      currentState = STANDBY;
      attendanceMode = "none";
      enrollmentActive = false;
      lastErrorMessage = "Ready";
      lastButtonPress = millis(); // IMPORTANT: reset so debounce doesn't re-fire immediately
      Serial.println("[BUTTON] Timeout. Reverting to STANDBY.");
    }
  }

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
  // Poll every 150ms - balanced speed and stability
  if (currentTime - lastImageGenTime < 150) {
    return;
  }
  lastImageGenTime = currentTime;

  // 1. Generate Image (Synchronous)
  uint8_t code = r307GenerateImage();
  server.handleClient();
  
  if (code != 0x02) { // 0x02 is the normal "no finger" code
    Serial.printf("[R307] GenerateImage returned: 0x%02X\n", code);
  }
  
  server.handleClient();
  
  // 2. Handle Wait for Remove state
  if (currentState == WAIT_REMOVE) {
    // Green LED is handled in handleEnrollingMode for this state to allow blinking Blue
    if (code == 0x02) { // No finger on sensor
      currentState = resumeStateAfterWaitRemove;
      resumeStateAfterWaitRemove = ENROLLING;
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
      // 3-step AS608 enroll: scan1->buf1, scan2->buf2, RegModel, scan3->buf2 (not buf1),
      // then RegModel again. Putting the 3rd image in buf1 overwrites the merged template and
      // can lead to failed Store (e.g. 0x18) or bad templates.
      uint8_t bufferId;
      if (currentScan + 1 >= MAX_SCANS) {
        bufferId = 2;
      } else {
        bufferId = (currentScan % 2 == 0) ? 1 : 2;
      }
      // Small settling gap: sensor needs ~20-30ms after GenerateImage before
      // accepting the next Img2Tz command, otherwise returns 0xFF (packet error).
      delay(30);
      while (fingerprintSerial.available()) fingerprintSerial.read();
      uint8_t res = r307Img2Tz(bufferId);
      if (res == 0x00) {
        if (currentScan + 1 >= MAX_SCANS) {
          // FINAL SCAN: build and store template
          Serial.println("[ENROLL] Final scan - running RegModel...");
          uint8_t regRes = r307RegModel();
          if (regRes == 0x00) {
            delay(50); // Give sensor time to settle after RegModel
            
            // Remove stale templates: web "remove" may not erase the module, so search can
            // match an old page (e.g. ID 3) while enrolling page 0. Delete non-target matches
            // until none remain or only our enrollment page matches.
            uint16_t finalDupID = 0;
            uint16_t finalScore = 0;
            for (int cleanup = 0; cleanup < 16; cleanup++) {
              uint8_t sr = r307Search(1, &finalDupID, &finalScore);
              if (sr != 0x00) {
                break;
              }
              if ((int)finalDupID == enrollmentSlotID) {
                break;
              }
              Serial.printf("[ENROLL] Dropping stale/conflicting page %u (enrolling %d)\n",
                            (unsigned)finalDupID, enrollmentSlotID);
              r307DeletePage(finalDupID);
              delay(80);
            }
            uint8_t searchRes = r307Search(1, &finalDupID, &finalScore);
            if (searchRes == 0x00 && (int)finalDupID != enrollmentSlotID) {
              matchedFingerprintID = finalDupID;
              triggerAuthFailed("Already registered (ID: " + String(finalDupID) + ")");
              return;
            }

            if (enrollmentSlotID < 0) {
              triggerAuthFailed("Invalid page index");
              return;
            }
            if (r307FingerprintCapacity > 0 && enrollmentSlotID >= (int)r307FingerprintCapacity) {
              triggerAuthFailed("Page index out of range (0-" + String((unsigned)(r307FingerprintCapacity - 1)) + ")");
              return;
            }
            delay(100); // Let RegModel settle before Store
            uint8_t storeRes = r307StoreModel(enrollmentSlotID);
            if (storeRes == 0x00) {
              lastErrorMessage = "Enrolled successfully";
              triggerFingerprintDetection();
            } else {
              String detail = "Store failed (0x" + String(storeRes, HEX) + ")";
              // 0x18 = FINGERPRINT_FLASHERR (flash write), not "bad slot" (that is usually 0x0B)
              if (storeRes == 0x18) {
                detail += " — flash write error: use a stable 5V supply, short wires, retry; "
                          "Clear All Fingerprints then wait a few seconds before enrolling.";
              }
              triggerAuthFailed(detail);
            }
          } else {
            triggerAuthFailed("RegModel failed (0x" + String(regRes, HEX) + ")");
          }
        } else {
          // INTERMEDIATE SCAN: If this is the first scan, we just move on.
          // If this is the second scan, we can optionally run an intermediate RegModel 
          // to strengthen the buffer, but for R307, the most stable way for 3 scans is:
          // 1. Scan 1 -> Buf 1
          // 2. Scan 2 -> Buf 2
          // 3. RegModel -> Result in Buf 1 & 2
          // 4. Scan 3 -> Buf 2
          // 5. Final RegModel -> Result in Buf 1 & 2
          
          if (currentScan == 1) { // This was the 2nd scan (currentScan 0->1)
             Serial.println("[ENROLL] Intermediate RegModel for Scan 1 & 2...");
             r307RegModel(); // Combine first two scans
             delay(50);
          }

          // confirm and wait for remove
          lastErrorMessage = "Scan " + String(currentScan + 1) + " complete. Remove finger.";
          triggerFingerprintDetection(); // increments currentScan and shows green LED
        }
      } else {
        triggerAuthFailed("Img2Tz failed (0x" + String(res, HEX) + ")");
      }
    } else if (currentState == VERIFYING) {
      server.handleClient();
      // Settle before Img2Tz to avoid 0xFF packet receive error
      delay(30);
      while (fingerprintSerial.available()) fingerprintSerial.read();
      uint8_t i2 = r307Img2Tz(1);
      server.handleClient();
      if (i2 != 0x00) {
        // Soft fail: single short error tone and wait for finger lift
        ledcWriteTone(BUZZER_LEDC_CHANNEL, 2000);
        ledcWrite(BUZZER_LEDC_CHANNEL, 120);
        delay(150);
        ledcWriteTone(BUZZER_LEDC_CHANNEL, 0);
        ledcWrite(BUZZER_LEDC_CHANNEL, 0);

        resumeStateAfterWaitRemove = VERIFYING;
        currentState = WAIT_REMOVE;
        lastErrorMessage = "Poor scan — lift finger and try again";
        return;
      }
      uint16_t fingerID = 0;
      uint16_t score = 0;
      uint8_t sr = r307Search(1, &fingerID, &score, verifySearchPageCount);
      server.handleClient();
      if (sr == 0x00) {
        matchedFingerprintID = (int)fingerID;
        lastErrorMessage = "Matched ID: " + String(fingerID);
        enrollmentActive = false;
        currentScan = MAX_SCANS;
        triggerFingerprintDetection();
      } else {
        // Not in library (wrong / unregistered): three beeps, then wait for finger lift and retry verify
        triggerAuthFailed("Fingerprint not recognized (not registered)", true);
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

// Read template library size (AS608 / R307 ReadSysPara — same layout as Adafruit_Fingerprint::getParameters)
bool r307RefreshFingerprintCapacity() {
  for (int attempt = 0; attempt < 3; attempt++) {
    clearR307Buffer();
    r307SendCommand(R307_CMD_READ_SYSPARA, NULL, 0);
    uint8_t response[64];
    uint16_t respLen = 0;
    if (!r307ReceiveResponse(response, &respLen, 1000)) {
      delay(50);
      continue;
    }
    if (response[6] != R307_ACK_PACKET || response[9] != 0x00) {
      delay(50);
      continue;
    }
    uint16_t cap = ((uint16_t)response[14] << 8) | response[15];
    if (cap >= 1 && cap <= 2000) {
      r307FingerprintCapacity = cap;
      Serial.printf("[R307] Library capacity: %u templates\n", (unsigned)r307FingerprintCapacity);
      return true;
    }
    delay(50);
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
  clearR307Buffer();
  r307SendCommand(R307_CMD_REG_MODEL, NULL, 0);
  uint8_t response[12];
  uint16_t respLen = 0;
  if (r307ReceiveResponse(response, &respLen, 2000)) { // Increased timeout for model generation
    return response[9];
  }
  return 0xFF;
}

uint8_t r307StoreModelFromBuffer(uint8_t charBuffer, uint16_t pageId) {
  clearR307Buffer();
  uint8_t data[3] = {charBuffer, (uint8_t)((pageId >> 8) & 0xFF), (uint8_t)(pageId & 0xFF)};
  r307SendCommand(R307_CMD_STORE, data, 3);
  uint8_t response[12];
  uint16_t respLen = 0;
  if (r307ReceiveResponse(response, &respLen, 5000)) {
    return response[9];
  }
  return 0xFF;
}

/** Delete one template page (same packet as HTTP /delete-fingerprint). Returns confirmation byte. */
uint8_t r307DeletePage(uint16_t pageId) {
  clearR307Buffer();
  uint8_t data[4] = {
    (uint8_t)((pageId >> 8) & 0xFF),
    (uint8_t)(pageId & 0xFF),
    0x00,
    0x01
  };
  r307SendCommand(R307_CMD_DELETE, data, 4);
  uint8_t response[12];
  uint16_t respLen = 0;
  if (r307ReceiveResponse(response, &respLen, 2000)) {
    return response[9];
  }
  return 0xFF;
}

uint8_t r307StoreModel(uint16_t id) {
  uint8_t last = 0xFF;
  for (int attempt = 0; attempt < 6; attempt++) {
    delay(80 + (uint32_t)attempt * 120);
    uint8_t r = r307StoreModelFromBuffer(1, id);
    last = r;
    if (r == 0x00) {
      return 0x00;
    }
    if (r != 0x18) {
      return r;
    }
    r = r307StoreModelFromBuffer(2, id);
    last = r;
    if (r == 0x00) {
      return 0x00;
    }
    if (r != 0x18) {
      return r;
    }
  }
  return last;
}

uint8_t r307Search(uint8_t bufferId, uint16_t* fingerID, uint16_t* score, uint16_t maxPagesOverride) {
  uint16_t searchCount = r307FingerprintCapacity > 0 ? r307FingerprintCapacity : 1000;
  if (searchCount > 1000) {
    searchCount = 1000;
  }
  if (maxPagesOverride > 0 && maxPagesOverride < searchCount) {
    searchCount = maxPagesOverride;
  }
  if (searchCount < 1) {
    searchCount = 1;
  }
  uint8_t data[5] = {
    bufferId,
    0x00,
    0x00,
    (uint8_t)(searchCount >> 8),
    (uint8_t)(searchCount & 0xFF)
  };
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

// ============= LCD SAFE HELPERS =============

/**
 * lcdSafeInit() — Reinitializes the HD44780 LCD controller.
 *
 * IMPORTANT: This function does NOT call Wire.end() or Wire.begin().
 * Calling Wire.end() during runtime kills the I2C peripheral and causes
 * the PCF8574 backpack to lose its output state → backlight turns off → blank screen.
 * Wire is initialized ONCE at boot in initializeHardware() and stays running forever.
 *
 * This function is safe to call from the periodic watchdog in updateLCD().
 */
void lcdSafeInit() {
  // Re-run the full HD44780 4-bit init sequence.
  // Two calls handle the case where RF/power noise left the controller mid-sequence.
  lcd.init();
  delay(5);
  lcd.init();
  delay(5);

  lcd.backlight(); // Ensure PCF8574 P3 (backlight) is HIGH
  lcd.display();   // Ensure display is on (DDRAM data shown on screen)
  lcd.noCursor();
  lcd.noBlink();

  // Invalidate text cache — forces a full redraw on next updateLCD() tick
  lastLCDLine1 = "";
  lastLCDLine2 = "";
  lastLCDReinitTime = millis();

  Serial.println("[LCD] Reinit complete.");
}

/**
 * lcdSafePrint() — Write two lines to the LCD without using lcd.clear().
 * Pads each string to exactly 16 characters so leftover characters from
 * a previous longer message are always overwritten cleanly.
 */
void lcdSafePrint(const String& line1, const String& line2) {
  String p1 = line1.substring(0, 16);
  String p2 = line2.substring(0, 16);
  while (p1.length() < 16) p1 += ' ';
  while (p2.length() < 16) p2 += ' ';

  lcd.setCursor(0, 0);
  lcd.print(p1);
  lcd.setCursor(0, 1);
  lcd.print(p2);

  // Keep cache in sync so updateLCD() won't immediately overwrite with stale values
  lastLCDLine1 = line1;
  lastLCDLine2 = line2;
}

// ============= LCD UPDATE LOGIC =============
void updateLCD() {
  unsigned long now = millis();

  // ---- Periodic Watchdog Reinit ----
  // Every 60 seconds, silently reinit the LCD controller to self-heal any
  // corruption caused by WiFi bursts, UART noise, or power glitches.
  // Only reinit during STANDBY so we don't interrupt an active scan.
  if (currentState == STANDBY && (now - lastLCDReinitTime >= 60000)) {
    lcdSafeInit();
    // After reinit, fall through to redraw immediately
  }

  // Update LCD every 500ms to avoid flicker but keep time snappy
  if (now - lastLCDUpdateTime < 500) return;
  lastLCDUpdateTime = now;

  const char* dayNames[] = {"Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"};
  String line1 = "";
  String line2 = "";

  switch(currentState) {
    case STANDBY:
      {
        // Alternate standby screen every 4 seconds
        bool showSystemTime = ((now / 4000) % 2 == 0);
        
        time_t epoch;
        time(&epoch);
        struct tm timeinfo;
        
        if (showSystemTime && epoch > 1000000000 && getLocalTime(&timeinfo, 50)) {
          char timeStr[15];
          strftime(timeStr, sizeof(timeStr), "%I:%M:%S %p", &timeinfo);
          line1 = "Barangay System";
          line2 = String(dayNames[timeinfo.tm_wday]) + " " + String(timeStr);
        } else {
          if (orangePiIP.toString() != "0.0.0.0") {
            line1 = "Web App IP:";
            line2 = orangePiIP.toString();
          } else {
            line1 = "Web App Address:";
            line2 = "brgysicosico.loc";
          }
        }
      }
      break;
    
    case ENROLLING:
      line1 = "ENROLLING...";
      line2 = "Scan " + String(currentScan + 1) + " of " + String(MAX_SCANS);
      break;

    case VERIFYING:
      if (attendanceMode == "in" || attendanceMode == "out") {
        String modeUpper = attendanceMode;
        modeUpper.toUpperCase();
        line1 = "TIME " + modeUpper + " Mode";
        line2 = "Place Finger...";
      } else if (attendanceMode == "attendance") {
        line1 = "ATTENDANCE MODE";
        line2 = "Place Finger...";
      } else {
        line1 = "LOGIN MODE";
        line2 = "Place finger...";
      }
      break;

    case FINGERPRINT_DETECTED:
      {
        String modeLabel = "";
        if (attendanceMode == "in") modeLabel = "TIME IN";
        else if (attendanceMode == "out") modeLabel = "TIME OUT";
        else modeLabel = "SCAN SUCCESS";
        line1 = modeLabel;
        time_t epoch;
        time(&epoch);
        struct tm timeinfo;
        if (epoch > 1000000000 && getLocalTime(&timeinfo, 50)) {
          char timeStr[12];
          strftime(timeStr, sizeof(timeStr), "%I:%M %p", &timeinfo);
          line2 = String(timeStr);
        } else {
          line2 = "Processing...";
        }
      }
      break;

    case WAIT_REMOVE:
      line1 = "PLEASE LIFT";
      line2 = "YOUR FINGER";
      break;

    case AUTH_FAILED:
      line1 = "SCAN FAILED";
      if (lastErrorMessage.indexOf("not recognized") != -1 || 
          lastErrorMessage.indexOf("not registered") != -1 || 
          lastErrorMessage.indexOf("Not registered") != -1) {
        line2 = "Not Registered";
      } else if (lastErrorMessage.indexOf("No Clock-In") != -1 || 
                 lastErrorMessage.indexOf("No Time In") != -1) {
        line2 = "No Clock-In!";
      } else if (lastErrorMessage.indexOf("Already Timed In") != -1 || 
                 lastErrorMessage.indexOf("Already Clocked In") != -1) {
        line2 = "Already ClockedIn";
      } else if (lastErrorMessage.indexOf("Already Timed Out") != -1 || 
                 lastErrorMessage.indexOf("Already Clocked Out") != -1) {
        line2 = "AlreadyClockedOut";
      } else {
        line2 = "Try Again...";
      }
      break;
  }

  // Only update hardware if text actually changed
  if (line1 != lastLCDLine1 || line2 != lastLCDLine2) {
    lcdSafePrint(line1, line2);
  }
}

// ============= ORANGE PI IP RESOLUTION =============
// No-op: Orange Pi is always at 10.42.0.1 on the Barangay_System_WiFi hotspot.
// IP is hardcoded at declaration — no runtime lookup needed.
void resolveOrangePiIP() {
  // orangePiIP = IPAddress(10, 42, 0, 1) is set at boot and never changes.
  Serial.println("[INFO] Orange Pi IP fixed at " ORANGE_PI_IP " (no lookup needed).");
}

// ============= ANNOUNCE IP TO DJANGO SERVER =============
void announceToServer() {
  if (WiFi.status() != WL_CONNECTED) return;
  if (orangePiIP.toString() == "0.0.0.0") return;
  
  // Try port 8000 first, then 8001 if needed. But for simplicity, we use the port learned if possible.
  // We'll try the known Django ports
  int portsToTry[] = {8000, 8001};
  String myIP = WiFi.localIP().toString();
  String payload = "{\"ip\":\"" + myIP + "\"}";
  
  for (int port : portsToTry) {
    String url = "http://" + orangePiIP.toString() + ":" + String(port) + "/api/esp32-heartbeat/";
    Serial.printf("[Heartbeat] Announcing IP %s to %s\n", myIP.c_str(), url.c_str());
    
    HTTPClient http;
    http.begin(url);
    http.setTimeout(2000); // 2 second timeout to avoid blocking main loop too long
    http.addHeader("Content-Type", "application/json");
    http.addHeader("X-ESP32-IP", myIP);
    int code = http.POST(payload);
    Serial.printf("[Heartbeat] Response on port %d: %d\n", port, code);
    http.end();
    
    if (code == 200 || code == 201 || code == 204) {
      lastAnnouncedOrangePiIP = orangePiIP;
      lastAnnouncedLocalIP = WiFi.localIP();
      break; // Success! No need to try other ports
    }
  }
}

// ============= SYSTEM STATUS PRINT =============
void printSystemStatus() {
  // Serial.println("\n================================");
  // Serial.println("SYSTEM STATUS");
  // Serial.println("================================");
  // Serial.printf("Current State: ");
  
  switch(currentState) {
    case STANDBY:
      // Serial.println("STANDBY (Blue LED slow blink - 1 second)");
      break;
    case ENROLLING:
      // Serial.println("ENROLLING (Blue LED fast blink - waiting for fingerprint)");
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
