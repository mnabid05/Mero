// Offline only. Uses the same board and single-thread search as UCI; games,
// not nodes within a game, are parallel. All bytes have an explicit endian.
using BulletRecord = std::array<unsigned char, 32>;

BulletRecord pack_bullet(const Board& b, int stm_cp) {
    if (std::popcount(b.occupied)>32 || stm_cp < -32767 || stm_cp > 32767)
        throw std::logic_error("position or score cannot be encoded");
    BulletRecord record{};
    unsigned count=0;
    // Engine square zero is a8. Bullet orients the mover at the bottom,
    // then enumerates occupied squares in ascending a1-based bit order.
    for (unsigned sq=0; sq<64; ++sq) {
        char pc=b.squares[sq ^ (b.white_to_move ? 56 : 0)];
        if (pc=='.') continue;
        int type=Zobrist::piece_index(pc)%6;
        bool ours=is_white(pc)==b.white_to_move;
        record[sq/8] |= 1U << (sq%8);
        record[8+count/2] |= (type | (ours ? 0 : 8)) << (4*(count%2));
        if (type==5) record[ours ? 27 : 28]=ours ? sq : (sq^56U);
        ++count;
    }
    uint16_t bits=static_cast<uint16_t>(stm_cp);
    record[24]=static_cast<unsigned char>(bits);
    record[25]=static_cast<unsigned char>(bits>>8);
    return record;  // WDL at byte 26 is filled only after the actual result.
}

struct GeneratedGame {
    std::string reason;
    int white_result=-1;  // 0/1/2 = loss/draw/win; -1 is incomplete
    std::vector<Move> moves;
    std::vector<unsigned> kept;
    std::vector<BulletRecord> rows;
};

GeneratedGame generate_game(uint64_t seed, unsigned game_id, unsigned nodes, int blend) {
    uint64_t rng=seed+uint64_t(game_id)*0x9e3779b97f4a7c15ULL;
    auto engine=std::make_unique<Engine>(8,blend);  // fresh TT & move histories per game
    Board board=Board::starting();
    std::vector<uint64_t> history{board.key};
    GeneratedGame game;
    for (;;) {
        const unsigned ply=static_cast<unsigned>(game.moves.size());
        const auto legal=board.legal_moves_in_place();
        if (legal.empty()) {
            bool mate=board.in_check();
            game.reason=mate ? "checkmate" : "stalemate";
            game.white_result=mate ? (board.white_to_move ? 0 : 2) : 1;
            break;
        }
        if (board.insufficient_material() || board.halfmove>=100 ||
                std::count(history.begin(),history.end(),board.key)>=3) {
            game.reason=board.insufficient_material() ? "material" :
                            board.halfmove>=100 ? "rule50" : "threefold";
            game.white_result=1;
            break;
        }
        if (ply==512) { game.reason="ply_cap"; break; }
        Move move;
        if (ply<8) {
            move=legal[splitmix64(rng)%legal.size()];
        } else {
            auto result=engine->search(board,MAX_PLY-2,2'000'000'000,history,nodes);
            move=result.move;
            if (std::find(legal.begin(),legal.end(),move)==legal.end())
                throw std::logic_error("search returned a nonlegal move");
            bool quiet=!board.in_check() && board.squares[move.to]=='.' &&
                       !(move.flags & EN_PASSANT) && !move.promotion;
            if (quiet && result.depth>0 && std::abs(result.score)<=30'000) {
                game.rows.push_back(pack_bullet(board,result.score));
                game.kept.push_back(ply);
            }
        }
        board.make_move(move);
        game.moves.push_back(move);
        history.push_back(board.key);
    }
    if (game.white_result<0) {
        game.rows.clear(); game.kept.clear(); // never invent a draw at the ply cap
    }
    for (size_t i=0;i<game.rows.size();++i)
        game.rows[i][26]=(game.kept[i]%2)==0 ? game.white_result : 2-game.white_result;
    return game;
}

uint64_t datagen_number(std::string_view arg,uint64_t lo,uint64_t hi) {
    uint64_t n=0;
    const auto [end,err]=std::from_chars(arg.data(),arg.data()+arg.size(),n);
    if (err!=std::errc{} || end!=arg.data()+arg.size() || n<lo || n>hi)
        throw std::invalid_argument("invalid numeric argument: "+std::string(arg));
    return n;
}

int datagen_main(int argc,char** argv) {
    if (argc!=8) throw std::invalid_argument(
        "datagen NEW_DIR GAMES NODES_PER_MOVE WORKERS SEED hce|active");
    const std::filesystem::path path(argv[2]);
    unsigned games=datagen_number(argv[3],1,1'000'000);
    unsigned nodes=datagen_number(argv[4],64,10'000'000);
    unsigned workers=datagen_number(argv[5],1,32);
    uint64_t seed=datagen_number(argv[6],0,UINT64_MAX);
    std::string mode=argv[7];
    if (mode!="hce" && mode!="active") throw std::invalid_argument("expected hce or active");
#ifdef MERO_SCRELU
    if (mode=="hce") throw std::invalid_argument("build with --release-control for HCE bootstrap");
#endif
    int blend=mode=="hce" ? 0 : DEFAULT_BLEND;
    if (!std::filesystem::create_directory(path)) throw std::runtime_error("output directory already exists");
    const auto output=[&](const char* name) {
        std::ofstream f;
        f.exceptions(std::ios::badbit | std::ios::failbit);
        f.open(path/name,std::ios::out | std::ios::binary);
        return f;
    };
    auto records=output("positions.bullet");
    auto ledger=output("games.tsv");
    ledger<<"game\twhite_wdl\ttermination\tfirst\trows\tkept_plies\tuci_moves\n";
    uint64_t total=0;
    unsigned completed=0;
    for (unsigned base=0;base<games;base+=workers) {
        // Bounded memory and stable file order independent of thread scheduling.
        std::vector<std::future<GeneratedGame>> batch;
        for (unsigned k=base;k<std::min(base+workers,games);++k)
            batch.emplace_back(std::async(std::launch::async,generate_game,seed,k,nodes,blend));
        for (unsigned k=0;k<batch.size();++k) {
            auto g=batch[k].get();
            for (const auto& r:g.rows)
                records.write(reinterpret_cast<const char*>(r.data()),r.size());
            ledger<<base+k<<'\t'<<g.white_result<<'\t'<<g.reason<<'\t'<<total<<'\t'<<g.rows.size()<<'\t';
            for (unsigned j=0;j<g.kept.size();++j) ledger<<(j ? "," : "")<<g.kept[j];
            ledger<<'\t';
            for (unsigned j=0;j<g.moves.size();++j) ledger<<(j ? " " : "")<<g.moves[j].uci();
            ledger<<'\n';
            total+=g.rows.size(); completed+=g.white_result>=0;
        }
    }
    records.close(); ledger.close();
    auto done=output("COMPLETE.json");
    done<<"{\"format\":\"bulletformat-chessboard-v1\",\"games\":"<<games
        <<",\"completed\":"<<completed<<",\"positions\":"<<total<<",\"seed\":"<<seed
        <<",\"workers\":"<<workers<<",\"nodes\":"<<nodes<<",\"opening_plies\":8,\"mode\":\""
        <<mode<<"\"}\n";
    done.close();
    std::cout<<completed<<'/'<<games<<" completed games; "<<total<<" labeled quiet positions\n";
    return 0;
}
