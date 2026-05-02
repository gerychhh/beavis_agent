#include "resolvers/AppResolver.h"

#include <cstdlib>
#include <fstream>
#include <limits>
#include <utility>
#include <vector>

#include <windows.h>

namespace {
std::string jsonString(const nlohmann::json& value, const std::string& key) {
    if (!value.contains(key) || !value.at(key).is_string()) {
        return "";
    }

    return value.at(key).get<std::string>();
}

bool jsonBool(const nlohmann::json& value, const std::string& key) {
    if (!value.contains(key) || !value.at(key).is_boolean()) {
        return false;
    }

    return value.at(key).get<bool>();
}

int jsonInt(const nlohmann::json& value, const std::string& key) {
    if (!value.contains(key) || !value.at(key).is_number_integer()) {
        return 0;
    }

    return value.at(key).get<int>();
}

std::filesystem::path moduleDirectory() {
    std::vector<wchar_t> buffer(MAX_PATH);

    while (true) {
        const DWORD length = GetModuleFileNameW(nullptr, buffer.data(), static_cast<DWORD>(buffer.size()));
        if (length == 0) {
            return std::filesystem::current_path();
        }

        if (length < buffer.size() - 1) {
            std::filesystem::path modulePath(buffer.data());
            return modulePath.parent_path();
        }

        buffer.resize(buffer.size() * 2);
    }
}

std::filesystem::path envPath(const char* name) {
    size_t size = 0;
    char* value = nullptr;
    if (_dupenv_s(&value, &size, name) != 0 || value == nullptr) {
        return {};
    }

    std::filesystem::path path(value);
    std::free(value);
    return path;
}
}

nlohmann::json AppLaunchTarget::toJson() const {
    return {
        {"app_id", appId},
        {"display_name", displayName},
        {"launch_type", launchType},
        {"launch_target", launchTarget},
        {"target_path", targetPath},
        {"arguments", arguments},
        {"working_directory", workingDirectory},
        {"source", source},
        {"exists", exists},
        {"priority", priority}
    };
}

AppResolver::AppResolver(std::filesystem::path indexPath)
    : indexPath_(indexPath.empty() ? defaultIndexPath() : std::move(indexPath)) {
}

std::filesystem::path AppResolver::indexPath() const {
    return indexPath_;
}

AppResolveResult AppResolver::resolve(const std::string& appId) const {
    if (appId.empty()) {
        return loadError("APP_ID_EMPTY", "app_id is empty");
    }

    if (!std::filesystem::exists(indexPath_)) {
        return loadError(
            "APP_INDEX_MISSING",
            "Apps index not found. Run: python -m python_agent.resolvers.app_indexer"
        );
    }

    std::ifstream file(indexPath_);
    if (!file) {
        return loadError("APP_INDEX_UNREADABLE", "Failed to open apps index");
    }

    nlohmann::json index;
    try {
        file >> index;
    } catch (const nlohmann::json::parse_error& error) {
        return loadError("APP_INDEX_INVALID", error.what());
    }

    if (!index.is_object() || !index.contains("records") || !index.at("records").is_array()) {
        return loadError("APP_INDEX_INVALID", "Index must contain records array");
    }

    AppLaunchTarget best;
    bool found = false;
    int bestPriority = std::numeric_limits<int>::min();

    for (const auto& record : index.at("records")) {
        if (!record.is_object()) {
            continue;
        }

        if (jsonString(record, "app_id") != appId) {
            continue;
        }

        if (!jsonBool(record, "exists")) {
            continue;
        }

        const std::string launchTarget = jsonString(record, "launch_target");
        if (launchTarget.empty()) {
            continue;
        }

        const int priority = jsonInt(record, "priority");
        if (!found || priority > bestPriority) {
            found = true;
            bestPriority = priority;
            best.appId = appId;
            best.displayName = jsonString(record, "display_name");
            best.launchType = jsonString(record, "launch_type");
            best.launchTarget = launchTarget;
            best.targetPath = jsonString(record, "target_path");
            best.arguments = jsonString(record, "arguments");
            best.workingDirectory = jsonString(record, "working_directory");
            best.source = jsonString(record, "source");
            best.exists = true;
            best.priority = priority;
        }
    }

    if (!found) {
        return loadError("APP_NOT_FOUND", "No existing launch target for app_id: " + appId);
    }

    AppResolveResult result;
    result.ok = true;
    result.target = std::move(best);
    return result;
}

std::filesystem::path AppResolver::defaultIndexPath() {
    const std::filesystem::path fromEnv = envPath("BEAVIS_APPS_INDEX");
    if (!fromEnv.empty()) {
        return fromEnv;
    }

    const std::filesystem::path relative = "python_agent/data/cache/apps_index.json";
    const std::vector<std::filesystem::path> candidates = {
        std::filesystem::current_path() / relative,
        moduleDirectory() / relative,
        moduleDirectory() / ".." / ".." / relative,
        moduleDirectory() / ".." / ".." / ".." / relative,
    };

    for (const auto& candidate : candidates) {
        const std::filesystem::path normalized = std::filesystem::weakly_canonical(candidate);
        if (std::filesystem::exists(normalized)) {
            return normalized;
        }
    }

    return std::filesystem::current_path() / relative;
}

AppResolveResult AppResolver::loadError(const std::string& code, const std::string& details) const {
    AppResolveResult result;
    result.ok = false;
    result.code = code;
    result.details = details + " (index: " + indexPath_.string() + ")";
    return result;
}
