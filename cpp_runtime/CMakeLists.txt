cmake_minimum_required(VERSION 3.20)

project(beavis_cpp_runtime LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

include(FetchContent)

FetchContent_Declare(
    nlohmann_json
    URL https://github.com/nlohmann/json/releases/download/v3.11.3/json.tar.xz
)

FetchContent_MakeAvailable(nlohmann_json)

add_executable(beavis_runtime
    src/main.cpp
    src/executor/ArgsValidator.cpp
    src/executor/Executor.cpp
    src/executor/SkillRegistry.cpp
    src/resolvers/AppResolver.cpp
    src/skills/apps/OpenAppSkill.cpp
    src/skills/system/VolumeSetSkill.cpp
    src/skills/web/WebOpenSkill.cpp
    src/skills/web/WebSearchSkill.cpp
    src/skills/windows/WindowControlSkill.cpp
    src/skills/windows/WindowLayoutSkill.cpp
    src/utils/WindowUtils.cpp
)

target_include_directories(beavis_runtime PRIVATE
    src
)

target_compile_definitions(beavis_runtime PRIVATE
    NOMINMAX
    WIN32_LEAN_AND_MEAN
)

target_link_libraries(beavis_runtime PRIVATE
    nlohmann_json::nlohmann_json
    Ole32
    Shell32
)
