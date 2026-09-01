#include "discovery.h"
#if defined(TAMA_ENABLE_HA_MQTT)

#include <ArduinoJson.h>

namespace tama::ha {

std::string buildDiscoveryPayload(const DiscoveryEntity& entity, const std::string& deviceId,
                                  const std::string& stateTopic,
                                  const std::string& availabilityTopic,
                                  const std::string& brandName, const std::string& fwVersion) {
  JsonDocument doc;
  doc["name"] = entity.name;
  doc["unique_id"] = "tamagooshi_" + deviceId + "_" + entity.objectId;
  doc["state_topic"] = stateTopic;
  doc["availability_topic"] = availabilityTopic;
  doc["payload_available"] = "online";
  doc["payload_not_available"] = "offline";
  if (entity.deviceClass[0] != '\0') doc["device_class"] = entity.deviceClass;
  if (entity.stateClass[0] != '\0') doc["state_class"] = entity.stateClass;

  JsonObject device = doc["device"].to<JsonObject>();
  JsonArray identifiers = device["identifiers"].to<JsonArray>();
  identifiers.add(deviceId);
  device["name"] = brandName + " (" + deviceId + ")";
  device["manufacturer"] = "Tamagooshi";
  device["model"] = "copilot";
  device["sw_version"] = fwVersion;

  std::string out;
  serializeJson(doc, out);
  return out;
}

}  // namespace tama::ha

#endif
