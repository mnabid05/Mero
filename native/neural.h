#pragma once
#include "mero_weights.h"
#include <algorithm>
#include <array>
#include <bit>
#include <cstdint>

namespace mero_neural {
using namespace mero_weights;
using Vector = std::array<std::int16_t, width>;
using Masks = std::array<std::uint64_t, 12>;

inline int flipped_feature(int piece, int square) {
    return ((piece + 6) % 12) * 64 + (square ^ 56);
}

struct Accumulator {
    Vector white{};
    Vector black{};

    void reset() {
        std::copy_n(bias, width, white.begin());
        black = white;
    }

    template<int sign>
    void change(int piece, int square) {
        const auto& w = features[piece * 64 + square];
        const auto& b = features[flipped_feature(piece, square)];
        for (int i = 0; i < width; ++i) {
            white[i] += sign * w[i];
            black[i] += sign * b[i];
        }
    }

    int residual() const {
        int dot = 0;
        for (int i = 0; i < width; ++i) {
            int w = std::clamp<int>(white[i], 0, input_scale);
            int b = std::clamp<int>(black[i], 0, input_scale);
            dot += (w - b) * head[i];
        }
        return static_cast<int>(static_cast<std::int64_t>(dot) * 512
                                / (input_scale * output_scale));
    }
};

class Evaluator {
    Accumulator sums;
    Masks previous{};

    template<int sign>
    void apply(int piece, std::uint64_t mask) {
        while (mask) {
            sums.change<sign>(piece, std::countr_zero(mask));
            mask &= mask - 1;
        }
    }

public:
    Evaluator() { sums.reset(); }

    int evaluate(const Masks& current) {
        // Removing before adding keeps each partial sum within the trained bound.
        for (int piece = 0; piece < 12; ++piece)
            apply<-1>(piece, previous[piece] & ~current[piece]);
        for (int piece = 0; piece < 12; ++piece)
            apply<1>(piece, current[piece] & ~previous[piece]);
        previous = current;
        return sums.residual();
    }
};
}
