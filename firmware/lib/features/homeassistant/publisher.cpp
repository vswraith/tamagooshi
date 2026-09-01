#include "publisher.h"
#if defined(TAMA_ENABLE_HA_MQTT)

#include "discovery.h"
#include "topics.h"

namespace tama {

namespace {

constexpr uint32_t kCheckIntervalMs = 250;

// Deliberately NOT derived from BuddyState.phase: that field includes a
// ~5s "Done" state the device uses purely for an on-screen confetti
// animation whenever running momentarily drops to 0 (e.g. the gap between
// one tool call finishing and the next starting) - it fires constantly
// mid-session, not just at true session end. HA cares whether a session is
// still open at all, so this derives straight from the session count the
// hub actually tracks (total), which only changes on real
// sessionStart/sessionEnd boundaries. No approval/waiting state is exposed
// here at all - HA is status-only, not approval tracking.
const char* haPhaseSlug(const BuddyState& b) {
  if (b.phase == BuddyPhase::Offline) return "offline";
  if (b.total > 0) return "working";
  return "idle";
}

}  // namespace

HaPublisher::HaPublisher(ITransport& mqtt, const DeviceState& state, std::string deviceId,
                         std::string brandName, std::string fwVersion)
    : mqtt_(mqtt),
      state_(state),
      deviceId_(std::move(deviceId)),
      brandName_(std::move(brandName)),
      fwVersion_(std::move(fwVersion)),
      availTopic_(ha_topics::availability(deviceId_)) {}

void HaPublisher::begin() {
  mqtt_.onConnection([this](bool connected) { onConnection(connected); });
  mqtt_.begin();
}

void HaPublisher::loop(uint32_t nowMs) {
  mqtt_.loop();
  if (nowMs - lastCheckMs_ < kCheckIntervalMs) return;
  lastCheckMs_ = nowMs;
  if (mqtt_.connected()) publishState(false);
}

void HaPublisher::onConnection(bool connected) {
  if (!connected) return;
  mqtt_.publish(availTopic_, "online", /*qos=*/1, /*retain=*/true);
  publishDiscovery();
  publishState(true);
}

void HaPublisher::publishDiscovery() {
  static const ha::DiscoveryEntity kEntities[] = {
      {"sensor", "phase", "Copilot Phase", "enum", ""},
      {"sensor", "status", "Copilot Status", "", ""},
      {"sensor", "running", "Copilot Running", "", "measurement"},
      {"sensor", "total", "Copilot Total", "", "measurement"},
  };
  for (const auto& entity : kEntities) {
    const std::string stateTopic = ha_topics::state(deviceId_, entity.objectId);
    const std::string payload = ha::buildDiscoveryPayload(entity, deviceId_, stateTopic,
                                                           availTopic_, brandName_, fwVersion_);
    mqtt_.publish(ha_topics::discoveryConfig(entity.component, deviceId_, entity.objectId),
                  payload, /*qos=*/1, /*retain=*/true);
  }
}

void HaPublisher::publishState(bool force) {
  const BuddyState& b = state_.buddy;
  const std::string phase = haPhaseSlug(b);

  // Only republish on a real session-boundary transition, not on every
  // individual tool call within a still-open session. The device's own
  // screen still shows every entry via the existing BLE buddy feed; HA
  // only needs the coarser picture.
  if (!force && phase == lastPhase_) return;

  mqtt_.publish(ha_topics::state(deviceId_, "phase"), phase, 1, true);
  mqtt_.publish(ha_topics::state(deviceId_, "status"), b.msg, 1, true);
  mqtt_.publish(ha_topics::state(deviceId_, "running"), std::to_string(b.running), 1, true);
  mqtt_.publish(ha_topics::state(deviceId_, "total"), std::to_string(b.total), 1, true);

  lastPhase_ = phase;
}

}  // namespace tama

#endif
