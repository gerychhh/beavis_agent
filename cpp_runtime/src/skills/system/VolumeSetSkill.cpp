#include "skills/system/VolumeSetSkill.h"

#include <algorithm>
#include <cmath>
#include <stdexcept>
#include <string>

#include <endpointvolume.h>
#include <mmdeviceapi.h>
#include <windows.h>

namespace {
class ComRuntime {
public:
    ComRuntime() {
        hr_ = CoInitializeEx(nullptr, COINIT_APARTMENTTHREADED);
        if (FAILED(hr_) && hr_ != RPC_E_CHANGED_MODE) {
            throw std::runtime_error("CoInitializeEx failed");
        }
    }

    ~ComRuntime() {
        if (SUCCEEDED(hr_)) {
            CoUninitialize();
        }
    }

private:
    HRESULT hr_;
};

template <typename T>
void releaseIfPresent(T* pointer) {
    if (pointer != nullptr) {
        pointer->Release();
    }
}

int scalarToPercent(float scalar) {
    const float clamped = std::clamp(scalar, 0.0f, 1.0f);
    return static_cast<int>(std::lround(clamped * 100.0f));
}

float percentToScalar(int percent) {
    const int clamped = std::clamp(percent, 0, 100);
    return static_cast<float>(clamped) / 100.0f;
}

class EndpointVolume {
public:
    EndpointVolume() {
        HRESULT hr = CoCreateInstance(
            __uuidof(MMDeviceEnumerator),
            nullptr,
            CLSCTX_ALL,
            IID_PPV_ARGS(&enumerator_)
        );
        if (FAILED(hr)) {
            throw std::runtime_error("Failed to create MMDeviceEnumerator");
        }

        hr = enumerator_->GetDefaultAudioEndpoint(eRender, eConsole, &device_);
        if (FAILED(hr)) {
            throw std::runtime_error("Failed to get default audio endpoint");
        }

        hr = device_->Activate(
            __uuidof(IAudioEndpointVolume),
            CLSCTX_ALL,
            nullptr,
            reinterpret_cast<void**>(&volume_)
        );
        if (FAILED(hr)) {
            throw std::runtime_error("Failed to activate IAudioEndpointVolume");
        }
    }

    ~EndpointVolume() {
        releaseIfPresent(volume_);
        releaseIfPresent(device_);
        releaseIfPresent(enumerator_);
    }

    int getPercent() const {
        float scalar = 0.0f;
        const HRESULT hr = volume_->GetMasterVolumeLevelScalar(&scalar);
        if (FAILED(hr)) {
            throw std::runtime_error("Failed to read current volume");
        }

        return scalarToPercent(scalar);
    }

    bool isMuted() const {
        BOOL muted = FALSE;
        const HRESULT hr = volume_->GetMute(&muted);
        if (FAILED(hr)) {
            throw std::runtime_error("Failed to read mute state");
        }

        return muted != FALSE;
    }

    void setMuted(bool muted) {
        const HRESULT hr = volume_->SetMute(muted ? TRUE : FALSE, nullptr);
        if (FAILED(hr)) {
            throw std::runtime_error("Failed to set mute state");
        }
    }

    void setPercent(int percent) {
        const int clampedPercent = std::clamp(percent, 0, 100);

        const HRESULT volumeHr = volume_->SetMasterVolumeLevelScalar(
            percentToScalar(clampedPercent),
            nullptr
        );
        if (FAILED(volumeHr)) {
            throw std::runtime_error("Failed to set volume");
        }

        // Important behavior:
        // 0% must be real system mute, not just volume level 0.
        // Any positive volume should automatically unmute the endpoint.
        setMuted(clampedPercent == 0);
    }

private:
    IMMDeviceEnumerator* enumerator_ = nullptr;
    IMMDevice* device_ = nullptr;
    IAudioEndpointVolume* volume_ = nullptr;
};
}

std::string VolumeSetSkill::name() const {
    return "volume_set";
}

std::string VolumeSetSkill::description() const {
    return "Sets or changes the system volume";
}

std::string VolumeSetSkill::riskLevel() const {
    return "low";
}

SkillResult VolumeSetSkill::execute(
    const nlohmann::json& args,
    RuntimeContext& context
) {
    (void)context;

    ComRuntime com;
    EndpointVolume endpointVolume;
    const int previousPercent = endpointVolume.getPercent();
    const bool previousMuted = endpointVolume.isMuted();
    const std::string mode = args.value("mode", "set");

    if (mode == "delta") {
        const int delta = args.at("delta").get<int>();
        const int newPercent = std::clamp(previousPercent + delta, 0, 100);
        endpointVolume.setPercent(newPercent);
        const bool muted = endpointVolume.isMuted();

        return SkillResult::ok(
            muted
                ? "Volume muted"
                : "Volume changed to " + std::to_string(newPercent),
            {
                {"mode", "delta"},
                {"delta", delta},
                {"previous_percent", previousPercent},
                {"previous_muted", previousMuted},
                {"percent", newPercent},
                {"muted", muted}
            }
        );
    }

    const int percent = std::clamp(args.at("percent").get<int>(), 0, 100);
    endpointVolume.setPercent(percent);
    const bool muted = endpointVolume.isMuted();

    return SkillResult::ok(
        muted
            ? "Volume muted"
            : "Volume set to " + std::to_string(percent),
        {
            {"mode", "set"},
            {"previous_percent", previousPercent},
            {"previous_muted", previousMuted},
            {"percent", percent},
            {"muted", muted}
        }
    );
}
