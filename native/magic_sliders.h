#pragma once
#include "slider_geometry.h"
#include "magic_numbers.h"
#include <bit>
#include <stdexcept>

namespace mero_sliders {
struct Entry { U64 mask; unsigned offset, shift; };
struct Tables {
    std::array<std::array<Entry,64>,2> entries{};
    std::array<U64,107648> hits{};
    Tables() {
        unsigned next = 0;
        for (int k = 0; k < 2; ++k) for (int s = 0; s < 64; ++s) {
            auto mask = trace(k,s,0,true);
            auto bits = static_cast<unsigned>(std::popcount(mask));
            entries[k][s] = {mask,next,64-bits};
            next += 1u << bits;
            if (next > hits.size()) throw std::logic_error("magic table overflow");
            U64 subset = 0;
            do {
                auto index = slot(k,s,subset);
                auto att = trace(k,s,subset);
                if (hits[index] && hits[index] != att) throw std::logic_error("magic collision");
                hits[index] = att;
                subset = (subset-mask)&mask;
            } while (subset);
        }
        if (next != hits.size()) throw std::logic_error("wrong magic table dimensions");
    }
    unsigned slot(int k, int s, U64 occupied) const {
        const auto& e = entries[k][s];
        return e.offset + (((occupied & e.mask) * factors[k][s]) >> e.shift);
    }
    U64 attacks(int k, int s, U64 occupied) const { return hits[slot(k,s,occupied)]; }
};
inline const Tables magic{};
constexpr auto between = [] {
    std::array<std::array<U64,64>,64> table{};
    for (int k=0;k<2;++k) for (int s=0;s<64;++s) for (const auto& d : steps[k]) {
        U64 previous = 0;
        for (int r=s/8+d[0], c=s%8+d[1]; inside(r,c); r+=d[0], c+=d[1]) {
            table[s][8*r+c] = previous;
            previous |= U64{1} << (8*r+c);
        }
    }
    return table;
}();
}
