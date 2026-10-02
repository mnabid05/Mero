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
    Board attack = Board::from_fen("6k1/5ppp/8/7Q/8/3B4/8/6K1 w - - 0 1");
    Board reflected = Board::from_fen("6k1/8/3b4/8/7q/8/5PPP/6K1 b - - 0 1");
    assert(Engine::king_pressure(attack) > 0);
    assert(Engine::king_pressure(attack) == -Engine::king_pressure(reflected));
    Board passer = Board::from_fen("7k/8/3P4/4K3/8/8/8/8 w - - 0 1");
    Board passer_reflected = Board::from_fen("8/8/8/8/4k3/3p4/8/7K b - - 0 1");
    assert(Engine::passed_pawn_activity(passer) > 0);
    assert(Engine::passed_pawn_activity(passer) == -Engine::passed_pawn_activity(passer_reflected));
    Board mate = Board::from_fen("7k/6Q1/5K2/8/8/8/8/8 b - - 100 1");
    auto mate_result = engine.search(mate, 4, 100);
    assert(mate_result.score == -MATE && !mate_result.move.valid());
    assert(engine.search(stale, 4, 100).score == 0);
    auto limited = engine.search(start, 64, 10000, {}, 1);
    assert(limited.nodes <= 1 && limited.move.valid());
    assert(start.fen() == Board::starting().fen());
    EnginePool pool(4);
    pool.set_threads(2);
    assert(pool.search(mate, 4, 100).score == -MATE);
    assert(pool.search(stale, 4, 100).score == 0);
    Board command_board = start;
    std::vector<uint64_t> command_history{start.key};
    try { parse_position(command_board, "position startpos moves e2e4 a8a1", command_history); }
    catch (const std::invalid_argument&) {}
    assert(command_board.fen() == start.fen());
    assert(command_history == std::vector<uint64_t>{start.key});
    parse_position(command_board, "position startpos moves e2e4 e7e5", command_history);
    assert(command_history.size() == 3);
    assert(command_history.back() == command_board.key);
    std::vector<uint64_t> history_test{1, 2, 3};
    {
        SuspendHistory suspend(history_test);
        assert(history_test == std::vector<uint64_t>({1, 2}));
        { HistoryGuard guard(history_test, 3); assert(history_test.size() == 3); }
        assert(history_test.size() == 2);
    }
    assert(history_test == std::vector<uint64_t>({1, 2, 3}));
    uint64_t random_state = 1729;
    for (int game = 0; game < 8; ++game) {
        Board walk = Board::starting();
        for (int ply = 0; ply < 100; ++ply) {
            auto legal = walk.legal_moves_in_place();
            std::string before = walk.fen();
            assert(walk.has_legal_move() == !legal.empty());
            assert(walk.fen() == before);
            assert(walk.key == ZOBRIST.hash(walk));
            if (legal.empty()) break;
            walk.make_move(legal[splitmix64(random_state) % legal.size()]);
        }
    }
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
