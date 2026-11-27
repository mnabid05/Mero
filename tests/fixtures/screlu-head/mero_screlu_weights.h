// Adversarial kernel fixture. Never build a playing engine with this header.
#pragma once
#include <array>
#include <cstdint>
namespace mero_screlu_weights {
inline constexpr int width=TEST_WIDTH;
inline constexpr std::int16_t bias[width]{},feature[768][width]{};
inline constexpr std::int16_t out_bias[8]{-32768,32767,-1,1,0,125,-125,0};
inline constexpr auto heads=[] {
    std::array<std::array<std::int16_t,2*width>,8> h{};
    for (int b=0;b<8;++b)
        for (int i=0;i<2*width;++i) {
            constexpr int bound=TEST_WIDE ? 32767 : 128;
            h[b][i]=b==0 ? bound : b==1 ? -bound : (i*43+b*11)%(2*bound+1)-bound;
        }
    if constexpr (TEST_WIDE) h[7][0]=-32768;
    return h;
}();
}
