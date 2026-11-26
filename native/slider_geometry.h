#pragma once
#include <array>
#include <cstdint>

namespace mero_sliders {
using U64 = std::uint64_t;
inline constexpr int steps[2][4][2] = {
    {{-1,-1},{-1,1},{1,-1},{1,1}},
    {{-1,0},{1,0},{0,-1},{0,1}}
};
constexpr bool inside(int r, int c) { return r >= 0 && r < 8 && c >= 0 && c < 8; }

// A blocker on the last square of a ray cannot change the attack set.
constexpr U64 trace(int kind, int sq, U64 blockers, bool relevant_only = false) {
    U64 hits = 0;
    for (auto& step : steps[kind]) {
        int r = sq / 8 + step[0], c = sq % 8 + step[1];
        while (inside(r,c)) {
            if (relevant_only && !inside(r+step[0], c+step[1])) break;
            U64 bit = U64{1} << (8*r+c);
            hits |= bit;
            if (blockers & bit) break;
            r += step[0];
            c += step[1];
        }
    }
    return hits;
}
}
