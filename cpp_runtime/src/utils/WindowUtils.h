#pragma once

#include <string>
#include <vector>

#include <windows.h>
#include <nlohmann/json.hpp>

namespace beavis::windows {

struct WindowInfo {
    HWND hwnd = nullptr;
    DWORD processId = 0;
    std::wstring title;
    std::wstring processPath;
    std::wstring processFile;
    int score = 0;
};

struct AppWindowTarget {
    std::string appId;
    std::wstring appIdWide;
    std::wstring displayName;
    std::wstring targetPath;
    std::wstring targetFile;
};

std::wstring utf8ToWide(const std::string& value);
std::string wideToUtf8(const std::wstring& value);
std::wstring lower(std::wstring value);
std::wstring filenameOf(const std::wstring& value);

bool isCandidateWindow(HWND hwnd);
std::vector<WindowInfo> listWindows();

AppWindowTarget makeAppWindowTarget(
    const std::string& appId,
    const std::string& displayName,
    const std::string& targetPath
);

bool findAppWindow(
    const std::string& appId,
    const AppWindowTarget& target,
    WindowInfo& out
);

bool showAndActivateWindow(HWND target);
nlohmann::json windowToJson(const WindowInfo& window);

}
