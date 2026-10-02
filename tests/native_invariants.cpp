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
    // Independently reproduced by both frozen native and Python generators.
    assert(perft(ep_pin, 3) == 4135);
    for (const Move& move : ep_pin.legal_moves()) assert(move.uci() != "c4d3");
    Board no_ep = Board::from_fen("8/6bb/8/8/R1pP2k1/4P3/P7/K7 b - - 0 1");
    assert(ep_pin.key == no_ep.key);
    Board legal_ep = Board::from_fen("4k3/8/8/3pP3/8/8/8/4K3 w - d6 0 1");
    assert(legal_ep.key != Board::from_fen("4k3/8/8/3pP3/8/8/8/4K3 w - - 0 1").key);
    assert(verify_keys(legal_ep, 3));
    assert(verify_keys(ep_pin, 3));
    Board late = Board::from_fen("4k3/8/8/8/8/8/8/R3K3 w - - 99 1");
    Board early = Board::from_fen("4k3/8/8/8/8/8/8/R3K3 w - - 0 1");
    assert(late.key == early.key);
    assert(late.search_key() != early.search_key());
    Board stale = Board::from_fen("7k/5Q2/6K1/8/8/8/8/8 b - - 0 1");
    assert(!stale.in_check() && !stale.has_legal_move());
    Engine engine(1);
    Board pinned = Board::from_fen("4k3/4r3/8/3p4/2B5/8/8/4R1K1 w - - 0 1");
    assert(engine.see(pinned, pinned.find_move("c4d5")) == 100);
    Board king_recapture = Board::from_fen("4k3/4p3/8/8/8/8/8/4R1K1 w - - 0 1");
    assert(engine.see(king_recapture, king_recapture.find_move("e1e7")) < 0);
    Board protected_capture = Board::from_fen("4k3/4p3/8/8/1B6/8/8/4R1K1 w - - 0 1");
    assert(engine.see(protected_capture, protected_capture.find_move("e1e7")) == 100);
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
