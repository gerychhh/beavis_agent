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

    void setPercent(int percent) {
        const HRESULT hr = volume_->SetMasterVolumeLevelScalar(
            percentToScalar(percent),
            nullptr
        );
        if (FAILED(hr)) {
            throw std::runtime_error("Failed to set volume");
        }
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
    const std::string mode = args.value("mode", "set");

    if (mode == "delta") {
        const int delta = args.at("delta").get<int>();
        const int newPercent = std::clamp(previousPercent + delta, 0, 100);
        endpointVolume.setPercent(newPercent);

        return SkillResult::ok(
            "Volume changed to " + std::to_string(newPercent),
            {
                {"mode", "delta"},
                {"delta", delta},
                {"previous_percent", previousPercent},
                {"percent", newPercent}
            }
        );
    }

    const int percent = args.at("percent").get<int>();
    endpointVolume.setPercent(percent);

    return SkillResult::ok(
        "Volume set to " + std::to_string(percent),
        {
            {"mode", "set"},
            {"previous_percent", previousPercent},
            {"percent", percent}
        }
    );
}
