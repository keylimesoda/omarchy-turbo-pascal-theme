#include <hyprland/src/version.h>
#include <iostream>
#include <string>
#include <string_view>

// Match PluginAPI.hpp's hash without its compositor-only global initializers.
std::string stripPatch(std::string_view version) {
    auto dot = version.find_last_of('.');
    return std::string(version.substr(0, dot));
}

int main() {
    std::cout << GIT_COMMIT_HASH;
#if defined(AQUAMARINE_VERSION) && defined(HYPRUTILS_VERSION) && \
    defined(HYPRGRAPHICS_VERSION) && defined(HYPRCURSOR_VERSION) && defined(HYPRLANG_VERSION)
    std::cout << "_aq_" << stripPatch(AQUAMARINE_VERSION)
              << "_hu_" << stripPatch(HYPRUTILS_VERSION)
              << "_hg_" << stripPatch(HYPRGRAPHICS_VERSION)
              << "_hc_" << stripPatch(HYPRCURSOR_VERSION)
              << "_hlg_" << stripPatch(HYPRLANG_VERSION);
#endif
    std::cout << '\n';
}
