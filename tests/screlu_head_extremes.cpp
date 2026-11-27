#include "screlu.h"
#include <array>
#include <cstdint>
static_assert(mero_screlu::compact_heads()==!TEST_WIDE);
int main() {
    using namespace mero_screlu_weights;
    mero_screlu::State state;
    constexpr std::array<int,8> values{-32768,-1,0,1,127,254,255,32767};
    for(int mode=0;mode<4;++mode) for(int b=0;b<8;++b) for(int stm=0;stm<2;++stm) {
        std::int64_t truth=out_bias[b]*255;
        for(int i=0;i<width;++i) {
            state.white[i]=mode==0?32767:mode==1?-32768:values[(i+3*b)%8];
            state.black[i]=mode==0?32767:mode==1?-32768:mode==2?values[(5*i+b)%8]:127;
            const int u=std::clamp<int>(stm?state.white[i]:state.black[i],0,255);
            const int t=std::clamp<int>(stm?state.black[i]:state.white[i],0,255);
            truth+=std::int64_t(u)*u*heads[b][i]+std::int64_t(t)*t*heads[b][i+width];
        }
        if(state.score({},stm,2+4*b)!=truth*400/(255*255*64)) return 1;
    }
}
