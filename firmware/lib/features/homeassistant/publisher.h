#pragma once
#if defined(TAMA_ENABLE_HA_MQTT)

#include <cstdint>
#include <string>

#include "model.h"
#include "transport.h"

namespace tama {

// Read-only status mirror: republishes DeviceState.buddy to a Home Assistant
// MQTT broker over WiFi, entirely independent of the BLE hub/agent channel
// used to actually talk to the Copilot hub. No inbound command topic - HA
// never controls anything here, it only observes.
class HaPublisher {
 public:
  HaPublisher(ITransport& mqtt, const DeviceState& state, std::string deviceId,
              std::string brandName, std::string fwVersion);

  void begin();
  void loop(uint32_t nowMs);

 private:
  void onConnection(bool connected);
  void publishDiscovery();
  void publishState(bool force);

  ITransport& mqtt_;
  const DeviceState& state_;
  std::string deviceId_;
  std::string brandName_;
  std::string fwVersion_;
  std::string availTopic_;

  uint32_t lastCheckMs_ = 0;

  // Last-published HA phase slug, gating republishes to session-boundary
  // transitions only (see publishState) - not the finer-grained
  // per-tool-call activity the device's own screen shows.
  std::string lastPhase_ = "offline";
};

}  // namespace tama

#endif
