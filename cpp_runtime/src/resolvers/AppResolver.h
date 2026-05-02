#pragma once

#include <filesystem>
#include <string>

#include <nlohmann/json.hpp>

struct AppLaunchTarget {
    std::string appId;
    std::string displayName;
    std::string launchType;
    std::string launchTarget;
    std::string targetPath;
    std::string arguments;
    std::string workingDirectory;
    std::string source;
    bool exists = false;
    int priority = 0;

    nlohmann::json toJson() const;
};

struct AppResolveResult {
    bool ok = false;
    AppLaunchTarget target;
    std::string code;
    std::string details;
};

class AppResolver {
public:
    explicit AppResolver(std::filesystem::path indexPath = {});

    AppResolveResult resolve(const std::string& appId) const;
    std::filesystem::path indexPath() const;

private:
    std::filesystem::path indexPath_;

    static std::filesystem::path defaultIndexPath();
    AppResolveResult loadError(const std::string& code, const std::string& details) const;
};
