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
    Board kiwi = Board::from_fen("r3k2r/p1ppqpb1/bn2pnp1/3PN3/1p2P3/2N2Q1p/PPPBBPPP/R3K2R w KQkq - 0 1");
    assert(perft(kiwi, 3) == 97862);
    Board ep_pin = Board::from_fen("8/6bb/8/8/R1pP2k1/4P3/P7/K7 b - d3 0 1");
    assert(perft(ep_pin, 3) == 1269);
    assert(Board::from_fen("4k3/8/8/8/8/8/8/2B1K3 w - - 0 1").insufficient_material());
    assert(!Board::from_fen("4k3/8/8/8/8/8/8/2B1KB2 w - - 0 1").insufficient_material());
    for (const char* fen : {
        "8/8/8/8/8/8/8/8 w - - 0 1",
        "4k3/8/8/8/8/8/8/4K3 x - - 0 1",
        "4k3/8/8/8/8/8/8/4K3 w KK - 0 1",
        "4k3/8/8/8/8/8/8/4K3 w - d6 0 1",
        "4k3/8/8/8/8/8/8/4K3 w - - -1 1",
        "4k3/88/8/8/8/8/4K3 w - - 0 1",
        "4x3/8/8/8/8/8/8/4K3 w - - 0 1"}) {
        bool rejected = false;
        try { (void)Board::from_fen(fen); }
        catch (const std::invalid_argument&) { rejected = true; }
        assert(rejected);
    }
    return 0;
}
