// Include the implementation so invariants exercise the real native board.
#define main mero_cli_main
#include "../native/engine.cpp"
#undef main
#include <cassert>

int main() {
    const std::string pieces = "PNBRQKpnbrqk";
    for (int i = 0; i < 12; ++i) assert(Zobrist::piece_index(pieces[i]) == i);
    Board start = Board::starting();
    assert(start.bitboards_valid());
    assert(start.key == ZOBRIST.hash(start));
    assert(perft(start, 4) == 197281);
    return 0;
}
