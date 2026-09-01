#pragma once
#if defined(TAMA_ENABLE_HA_MQTT)

#include <string>

// Deliberately separate from lib/wire/protocol/topics.h's devices/<id>/...
// tree (the hub-protocol topics) so there's no collision if a brand ever
// runs both the MQTT hub carrier and this side-channel HA publisher.
namespace tama::ha_topics {

inline std::string discoveryConfig(const std::string& component, const std::string& deviceId,
                                   const std::string& objectId) {
  return "homeassistant/" + component + "/tamagooshi_" + deviceId + "/" + objectId + "/config";
}

inline std::string state(const std::string& deviceId, const std::string& key) {
  return "tamagooshi/" + deviceId + "/" + key;
}

inline std::string availability(const std::string& deviceId) {
  return "tamagooshi/" + deviceId + "/availability";
}

}  // namespace tama::ha_topics

#endif
