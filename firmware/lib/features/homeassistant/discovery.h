#pragma once
#if defined(TAMA_ENABLE_HA_MQTT)

#include <string>

namespace tama::ha {

struct DiscoveryEntity {
  const char* component;    // "sensor", "binary_sensor", ...
  const char* objectId;     // "phase", "status", "running", "total"
  const char* name;         // "Copilot Phase"
  const char* deviceClass;  // "" if none
  const char* stateClass;   // "" if none, else "measurement"
};

// Builds the HA MQTT discovery config JSON payload for one entity, grouping
// it under a single HA device card (identified by deviceId) alongside the
// device's other entities.
std::string buildDiscoveryPayload(const DiscoveryEntity& entity, const std::string& deviceId,
                                  const std::string& stateTopic,
                                  const std::string& availabilityTopic,
                                  const std::string& brandName, const std::string& fwVersion);

}  // namespace tama::ha

#endif
