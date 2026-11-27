#pragma once
#include "mero_screlu_weights.h" // Generated and validated in the build directory.
#include <algorithm>
#include <array>
#include <bit>
#include <cstdint>
#if !defined(MERO_SCALAR_ONLY) && (defined(__AVX2__) || defined(__AVX512BW__))
#include <immintrin.h>
#elif !defined(MERO_SCALAR_ONLY) && defined(__ARM_NEON)
#include <arm_neon.h>
#endif

namespace mero_screlu {
using Masks = std::array<std::uint64_t,12>;
using Vector = std::array<std::int16_t,mero_screlu_weights::width>;

// Never change or clip a weight to select the faster kernel. A checkpoint
// outside this proven range goes through the original wide dot product.
constexpr bool compact_heads() {
    for (const auto& head : mero_screlu_weights::heads)
        for (auto w : head) if (w < -128 || w > 128) return false;
    return true;
}

#if !defined(MERO_SCALAR_ONLY) && defined(__ARM_NEON) && defined(__aarch64__)
inline std::int64_t compact_dot(const Vector& input,const std::int16_t* weights) {
    static_assert(mero_screlu_weights::width%8==0);
    // The first multiply fits i16 (255*128); each i32 lane sums width/8
    // signed terms of magnitude at most 255*255*128. Widen before reduction.
    static_assert((mero_screlu_weights::width/8)*255LL*255*128 < (1LL<<31));
    int32x4_t lo=vdupq_n_s32(0), hi=vdupq_n_s32(0);
    for (int i=0;i<mero_screlu_weights::width;i+=8) {
        const auto x=vminq_s16(vmaxq_s16(vld1q_s16(input.data()+i),vdupq_n_s16(0)),vdupq_n_s16(255));
        const auto weighted=vmulq_s16(x,vld1q_s16(weights+i));
        lo=vmlal_s16(lo,vget_low_s16(x),vget_low_s16(weighted));
        hi=vmlal_high_s16(hi,x,weighted);
    }
    return vaddlvq_s32(lo)+vaddlvq_s32(hi);
}
#endif

template<bool add>
inline void apply(Vector& v,const std::int16_t* w) {
#if !defined(MERO_SCALAR_ONLY) && defined(__AVX512BW__)
    for (int i=0;i<mero_screlu_weights::width;i+=32) {
        auto x=_mm512_loadu_si512(v.data()+i), y=_mm512_loadu_si512(w+i);
        _mm512_storeu_si512(v.data()+i,add?_mm512_add_epi16(x,y):_mm512_sub_epi16(x,y));
    }
#elif !defined(MERO_SCALAR_ONLY) && defined(__AVX2__)
    for (int i=0;i<mero_screlu_weights::width;i+=16) {
        auto x=_mm256_loadu_si256(reinterpret_cast<const __m256i*>(v.data()+i));
        auto y=_mm256_loadu_si256(reinterpret_cast<const __m256i*>(w+i));
        _mm256_storeu_si256(reinterpret_cast<__m256i*>(v.data()+i),
                            add?_mm256_add_epi16(x,y):_mm256_sub_epi16(x,y));
    }
#elif !defined(MERO_SCALAR_ONLY) && defined(__ARM_NEON)
    for (int i=0;i<mero_screlu_weights::width;i+=8) {
        auto x=vld1q_s16(v.data()+i), y=vld1q_s16(w+i);
        vst1q_s16(v.data()+i,add?vaddq_s16(x,y):vsubq_s16(x,y));
    }
#else
    for (int i=0;i<mero_screlu_weights::width;++i) v[i] += add?w[i]:-w[i];
#endif
}

// The board owns its state, including on scratch copies and parallel workers.
// Changes commute and cancel: legality probes need no 512-lane update when
// made and unmade before evaluation. No parent pointer or shared mutable net.
struct State {
    alignas(64) Vector white,black;
    Masks dirty{};
    State() { reset({}); }

    void reset(const Masks& occupied) {
        std::copy_n(mero_screlu_weights::bias,mero_screlu_weights::width,white.begin());
        black=white;
        dirty=occupied;
    }
    void toggle(int piece,int square) { dirty[piece] ^= std::uint64_t{1} << square; }

    template<bool add> void change(int piece,std::uint64_t bits) {
        while (bits) {
            int sq=std::countr_zero(bits);
            apply<add>(white,mero_screlu_weights::feature[piece*64+sq]);
            apply<add>(black,mero_screlu_weights::feature[((piece+6)%12)*64+(sq^56)]);
            bits &= bits-1;
        }
    }

    int score(const Masks& pieces,bool white_to_move,int count) {
        for (int p=0;p<12;++p) change<false>(p,dirty[p]&~pieces[p]);
        for (int p=0;p<12;++p) {
            change<true>(p,dirty[p]&pieces[p]);
            dirty[p]=0;
        }
        int bucket=std::clamp((count-2)/4,0,7);
        const auto& us=white_to_move?white:black;
        const auto& them=white_to_move?black:white;
        const auto& h=mero_screlu_weights::heads[bucket];
        std::int64_t sum=mero_screlu_weights::out_bias[bucket]*255;
#if !defined(MERO_SCALAR_ONLY) && defined(__ARM_NEON) && defined(__aarch64__)
        if constexpr (compact_heads()) {
            sum+=compact_dot(us,&h[0])+compact_dot(them,&h[mero_screlu_weights::width]);
            return static_cast<int>(sum*400/(255*255*64));
        }
#endif
        for (int i=0;i<mero_screlu_weights::width;++i) {
            int u=std::clamp<int>(us[i],0,255), t=std::clamp<int>(them[i],0,255);
            sum += std::int64_t(u*u)*h[i] + std::int64_t(t*t)*h[i+mero_screlu_weights::width];
        }
        return static_cast<int>(sum*400/(255*255*64));
    }
};
}
