#include <algorithm>
#include <array>
#include <chrono>
#include <cctype>
#include <cmath>
#include <cstdint>
#include <cstdlib>
#include <iostream>
#include <limits>
#include <sstream>
#include <stdexcept>
#include <string>
#include <unordered_map>
#include <utility>
#include <vector>

extern "C" int mwahaha_evaluate(const char board[64]);

namespace {

constexpr int INF = 1'000'000;
constexpr int MATE = 100'000;
constexpr int MAX_PLY = 96;
constexpr int WHITE_KING_SIDE = 1;
constexpr int WHITE_QUEEN_SIDE = 2;
constexpr int BLACK_KING_SIDE = 4;
constexpr int BLACK_QUEEN_SIDE = 8;
constexpr int EN_PASSANT = 1;
constexpr int CASTLING = 2;

constexpr std::array<int, 128> PIECE_VALUES = [] {
    std::array<int, 128> values{};
    values['p'] = values['P'] = 100;
    values['n'] = values['N'] = 325;
    values['b'] = values['B'] = 335;
    values['r'] = values['R'] = 500;
    values['q'] = values['Q'] = 975;
    values['k'] = values['K'] = 20'000;
    return values;
}();

bool is_white(char piece) {
    return piece >= 'A' && piece <= 'Z';
}

bool same_color(char left, char right) {
    return left != '.' && right != '.' && is_white(left) == is_white(right);
}

int square_from_name(const std::string& name) {
    if (name.size() != 2 || name[0] < 'a' || name[0] > 'h'
        || name[1] < '1' || name[1] > '8') {
        throw std::invalid_argument("invalid square: " + name);
    }
    return (8 - (name[1] - '0')) * 8 + (name[0] - 'a');
}

std::string square_name(int square) {
    std::string result = "a8";
    result[0] = static_cast<char>('a' + square % 8);
    result[1] = static_cast<char>('8' - square / 8);
    return result;
}

struct Move {
    int from = -1;
    int to = -1;
    char promotion = '\0';
    int flags = 0;

    std::string uci() const {
        if (from < 0 || to < 0) {
            return "0000";
        }
        std::string result = square_name(from) + square_name(to);
        if (promotion != '\0') {
            result.push_back(
                static_cast<char>(std::tolower(static_cast<unsigned char>(promotion)))
            );
        }
        return result;
    }

    bool operator==(const Move& other) const {
        return from == other.from && to == other.to
            && promotion == other.promotion && flags == other.flags;
    }

    bool valid() const {
        return from >= 0;
    }
};

struct Board {
    std::array<char, 64> squares{};
    bool white_to_move = true;
    int castling = WHITE_KING_SIDE | WHITE_QUEEN_SIDE
        | BLACK_KING_SIDE | BLACK_QUEEN_SIDE;
    int en_passant = -1;
    int halfmove = 0;
    int fullmove = 1;

    Board() {
        squares.fill('.');
    }

    static Board from_fen(const std::string& fen) {
        std::istringstream input(fen);
        std::string placement;
        std::string turn;
        std::string rights;
        std::string ep;
        Board board;
        if (!(input >> placement >> turn >> rights >> ep
            >> board.halfmove >> board.fullmove)) {
            throw std::invalid_argument("FEN must contain six fields");
        }

        int square = 0;
        for (char token : placement) {
            if (token == '/') {
                continue;
            }
            if (std::isdigit(static_cast<unsigned char>(token))) {
                square += token - '0';
            } else {
                if (square >= 64) {
                    throw std::invalid_argument("invalid FEN placement");
                }
                board.squares[square++] = token;
            }
        }
        if (square != 64) {
            throw std::invalid_argument("invalid FEN square count");
        }
        board.white_to_move = turn == "w";
        board.castling = 0;
        if (rights.find('K') != std::string::npos) {
            board.castling |= WHITE_KING_SIDE;
        }
        if (rights.find('Q') != std::string::npos) {
            board.castling |= WHITE_QUEEN_SIDE;
        }
        if (rights.find('k') != std::string::npos) {
            board.castling |= BLACK_KING_SIDE;
        }
        if (rights.find('q') != std::string::npos) {
            board.castling |= BLACK_QUEEN_SIDE;
        }
        board.en_passant = ep == "-" ? -1 : square_from_name(ep);
        return board;
    }

    static Board starting() {
        return from_fen(
            "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"
        );
    }

    std::string fen() const {
        std::ostringstream output;
        for (int row = 0; row < 8; ++row) {
            int empty = 0;
            for (int column = 0; column < 8; ++column) {
                char piece = squares[row * 8 + column];
                if (piece == '.') {
                    ++empty;
                } else {
                    if (empty != 0) {
                        output << empty;
                        empty = 0;
                    }
                    output << piece;
                }
            }
            if (empty != 0) {
                output << empty;
            }
            if (row != 7) {
                output << '/';
            }
        }
        output << (white_to_move ? " w " : " b ");
        if (castling == 0) {
            output << '-';
        } else {
            if (castling & WHITE_KING_SIDE) output << 'K';
            if (castling & WHITE_QUEEN_SIDE) output << 'Q';
            if (castling & BLACK_KING_SIDE) output << 'k';
            if (castling & BLACK_QUEEN_SIDE) output << 'q';
        }
        output << ' ' << (en_passant < 0 ? "-" : square_name(en_passant));
        output << ' ' << halfmove << ' ' << fullmove;
        return output.str();
    }

    bool attacked(int target, bool by_white) const {
        int row = target / 8;
        int column = target % 8;
        int pawn_source_row = row + (by_white ? 1 : -1);
        char pawn = by_white ? 'P' : 'p';
        for (int delta : {-1, 1}) {
            int source_column = column + delta;
            if (pawn_source_row >= 0 && pawn_source_row < 8
                && source_column >= 0 && source_column < 8
                && squares[pawn_source_row * 8 + source_column] == pawn) {
                return true;
            }
        }

        constexpr int knight_offsets[8][2] = {
            {-2, -1}, {-2, 1}, {-1, -2}, {-1, 2},
            {1, -2}, {1, 2}, {2, -1}, {2, 1}
        };
        char knight = by_white ? 'N' : 'n';
        for (const auto& offset : knight_offsets) {
            int source_row = row + offset[0];
            int source_column = column + offset[1];
            if (source_row >= 0 && source_row < 8
                && source_column >= 0 && source_column < 8
                && squares[source_row * 8 + source_column] == knight) {
                return true;
            }
        }

        constexpr int directions[8][2] = {
            {-1, -1}, {-1, 1}, {1, -1}, {1, 1},
            {-1, 0}, {1, 0}, {0, -1}, {0, 1}
        };
        char king = by_white ? 'K' : 'k';
        for (int index = 0; index < 8; ++index) {
            int source_row = row + directions[index][0];
            int source_column = column + directions[index][1];
            if (source_row >= 0 && source_row < 8
                && source_column >= 0 && source_column < 8
                && squares[source_row * 8 + source_column] == king) {
                return true;
            }
            while (source_row >= 0 && source_row < 8
                && source_column >= 0 && source_column < 8) {
                char piece = squares[source_row * 8 + source_column];
                if (piece != '.') {
                    if (is_white(piece) == by_white) {
                        char type = static_cast<char>(std::tolower(piece));
                        bool diagonal = index < 4;
                        if (type == 'q'
                            || (diagonal && type == 'b')
                            || (!diagonal && type == 'r')) {
                            return true;
                        }
                    }
                    break;
                }
                source_row += directions[index][0];
                source_column += directions[index][1];
            }
        }
        return false;
    }

    int king_square(bool white) const {
        char king = white ? 'K' : 'k';
        auto found = std::find(squares.begin(), squares.end(), king);
        return found == squares.end()
            ? -1
            : static_cast<int>(std::distance(squares.begin(), found));
    }

    bool in_check(bool white) const {
        int king = king_square(white);
        return king >= 0 && attacked(king, !white);
    }

    bool in_check() const {
        return in_check(white_to_move);
    }

    void add_promotions(std::vector<Move>& moves, int from, int to, int flags) const {
        for (char promotion : {'q', 'r', 'b', 'n'}) {
            moves.push_back({from, to, promotion, flags});
        }
    }

    std::vector<Move> pseudo_moves(bool captures_only = false) const {
        std::vector<Move> moves;
        moves.reserve(64);
        constexpr int knight_offsets[8][2] = {
            {-2, -1}, {-2, 1}, {-1, -2}, {-1, 2},
            {1, -2}, {1, 2}, {2, -1}, {2, 1}
        };
        constexpr int directions[8][2] = {
            {-1, -1}, {-1, 1}, {1, -1}, {1, 1},
            {-1, 0}, {1, 0}, {0, -1}, {0, 1}
        };

        for (int from = 0; from < 64; ++from) {
            char piece = squares[from];
            if (piece == '.' || is_white(piece) != white_to_move) {
                continue;
            }
            char type = static_cast<char>(std::tolower(piece));
            int row = from / 8;
            int column = from % 8;
            if (type == 'p') {
                int direction = white_to_move ? -1 : 1;
                int promotion_row = white_to_move ? 0 : 7;
                int start_row = white_to_move ? 6 : 1;
                int next_row = row + direction;
                if (!captures_only && next_row >= 0 && next_row < 8) {
                    int one = next_row * 8 + column;
                    if (squares[one] == '.') {
                        if (next_row == promotion_row) {
                            add_promotions(moves, from, one, 0);
                        } else {
                            moves.push_back({from, one, '\0', 0});
                            int two = (row + 2 * direction) * 8 + column;
                            if (row == start_row && squares[two] == '.') {
                                moves.push_back({from, two, '\0', 0});
                            }
                        }
                    }
                }
                for (int delta : {-1, 1}) {
                    int target_column = column + delta;
                    if (next_row < 0 || next_row >= 8
                        || target_column < 0 || target_column >= 8) {
                        continue;
                    }
                    int to = next_row * 8 + target_column;
                    bool capture = squares[to] != '.' && !same_color(piece, squares[to]);
                    if (!capture && to != en_passant) {
                        continue;
                    }
                    int flags = to == en_passant ? EN_PASSANT : 0;
                    if (next_row == promotion_row) {
                        add_promotions(moves, from, to, flags);
                    } else {
                        moves.push_back({from, to, '\0', flags});
                    }
                }
            } else if (type == 'n' || type == 'k') {
                const int (*offsets)[2] =
                    type == 'n' ? knight_offsets : directions;
                for (int index = 0; index < 8; ++index) {
                    int target_row = row + offsets[index][0];
                    int target_column = column + offsets[index][1];
                    if (target_row < 0 || target_row >= 8
                        || target_column < 0 || target_column >= 8) {
                        continue;
                    }
                    int to = target_row * 8 + target_column;
                    char target = squares[to];
                    if (target == '.') {
                        if (!captures_only) {
                            moves.push_back({from, to, '\0', 0});
                        }
                    } else if (!same_color(piece, target)) {
                        moves.push_back({from, to, '\0', 0});
                    }
                }
                if (type == 'k' && !captures_only && !in_check()) {
                    if (white_to_move && from == 60) {
                        if ((castling & WHITE_KING_SIDE) && squares[61] == '.'
                            && squares[62] == '.' && squares[63] == 'R'
                            && !attacked(61, false) && !attacked(62, false)) {
                            moves.push_back({60, 62, '\0', CASTLING});
                        }
                        if ((castling & WHITE_QUEEN_SIDE) && squares[59] == '.'
                            && squares[58] == '.' && squares[57] == '.'
                            && squares[56] == 'R'
                            && !attacked(59, false) && !attacked(58, false)) {
                            moves.push_back({60, 58, '\0', CASTLING});
                        }
                    } else if (!white_to_move && from == 4) {
                        if ((castling & BLACK_KING_SIDE) && squares[5] == '.'
                            && squares[6] == '.' && squares[7] == 'r'
                            && !attacked(5, true) && !attacked(6, true)) {
                            moves.push_back({4, 6, '\0', CASTLING});
                        }
                        if ((castling & BLACK_QUEEN_SIDE) && squares[3] == '.'
                            && squares[2] == '.' && squares[1] == '.'
                            && squares[0] == 'r'
                            && !attacked(3, true) && !attacked(2, true)) {
                            moves.push_back({4, 2, '\0', CASTLING});
                        }
                    }
                }
            } else {
                int start = type == 'b' ? 0 : (type == 'r' ? 4 : 0);
                int stop = type == 'b' ? 4 : (type == 'r' ? 8 : 8);
                for (int index = start; index < stop; ++index) {
                    int target_row = row + directions[index][0];
                    int target_column = column + directions[index][1];
                    while (target_row >= 0 && target_row < 8
                        && target_column >= 0 && target_column < 8) {
                        int to = target_row * 8 + target_column;
                        char target = squares[to];
                        if (target == '.') {
                            if (!captures_only) {
                                moves.push_back({from, to, '\0', 0});
                            }
                        } else {
                            if (!same_color(piece, target)) {
                                moves.push_back({from, to, '\0', 0});
                            }
                            break;
                        }
                        target_row += directions[index][0];
                        target_column += directions[index][1];
                    }
                }
            }
        }
        return moves;
    }

    void make_move(const Move& move) {
        char piece = squares[move.from];
        bool moving_white = is_white(piece);
        char captured = squares[move.to];
        int captured_square = move.to;
        if (move.flags & EN_PASSANT) {
            captured_square = move.to + (moving_white ? 8 : -8);
            captured = squares[captured_square];
            squares[captured_square] = '.';
        }

        squares[move.from] = '.';
        squares[move.to] = move.promotion == '\0'
            ? piece
            : static_cast<char>(
                moving_white ? std::toupper(move.promotion) : move.promotion
            );

        if (move.flags & CASTLING) {
            if (move.to == 62) {
                squares[61] = squares[63];
                squares[63] = '.';
            } else if (move.to == 58) {
                squares[59] = squares[56];
                squares[56] = '.';
            } else if (move.to == 6) {
                squares[5] = squares[7];
                squares[7] = '.';
            } else if (move.to == 2) {
                squares[3] = squares[0];
                squares[0] = '.';
            }
        }

        if (piece == 'K') castling &= ~(WHITE_KING_SIDE | WHITE_QUEEN_SIDE);
        if (piece == 'k') castling &= ~(BLACK_KING_SIDE | BLACK_QUEEN_SIDE);
        if (move.from == 63 || captured_square == 63) castling &= ~WHITE_KING_SIDE;
        if (move.from == 56 || captured_square == 56) castling &= ~WHITE_QUEEN_SIDE;
        if (move.from == 7 || captured_square == 7) castling &= ~BLACK_KING_SIDE;
        if (move.from == 0 || captured_square == 0) castling &= ~BLACK_QUEEN_SIDE;

        en_passant = -1;
        if (std::tolower(piece) == 'p' && std::abs(move.to - move.from) == 16) {
            en_passant = (move.from + move.to) / 2;
        }
        halfmove = (std::tolower(piece) == 'p' || captured != '.')
            ? 0
            : halfmove + 1;
        if (!moving_white) {
            ++fullmove;
        }
        white_to_move = !white_to_move;
    }

    std::vector<Move> legal_moves(bool captures_only = false) const {
        std::vector<Move> legal;
        bool moving_white = white_to_move;
        for (const Move& move : pseudo_moves(captures_only)) {
            Board child = *this;
            child.make_move(move);
            if (!child.in_check(moving_white)) {
                legal.push_back(move);
            }
        }
        return legal;
    }

    Move find_move(const std::string& uci) const {
        for (const Move& move : legal_moves()) {
            if (move.uci() == uci) {
                return move;
            }
        }
        throw std::invalid_argument("illegal move: " + uci);
    }
};

uint64_t splitmix64(uint64_t& state) {
    uint64_t value = (state += 0x9e3779b97f4a7c15ULL);
    value = (value ^ (value >> 30)) * 0xbf58476d1ce4e5b9ULL;
    value = (value ^ (value >> 27)) * 0x94d049bb133111ebULL;
    return value ^ (value >> 31);
}

struct Zobrist {
    std::array<std::array<uint64_t, 64>, 12> pieces{};
    std::array<uint64_t, 16> castling{};
    std::array<uint64_t, 8> ep_file{};
    uint64_t turn = 0;

    Zobrist() {
        uint64_t state = 0x4d77616861686121ULL;
        for (auto& piece : pieces) {
            for (uint64_t& square : piece) {
                square = splitmix64(state);
            }
        }
        for (uint64_t& value : castling) value = splitmix64(state);
        for (uint64_t& value : ep_file) value = splitmix64(state);
        turn = splitmix64(state);
    }

    static int piece_index(char piece) {
        std::string symbols = "PNBRQKpnbrqk";
        return static_cast<int>(symbols.find(piece));
    }

    uint64_t hash(const Board& board) const {
        uint64_t key = 0;
        for (int square = 0; square < 64; ++square) {
            if (board.squares[square] != '.') {
                key ^= pieces[piece_index(board.squares[square])][square];
            }
        }
        key ^= castling[board.castling];
        if (board.en_passant >= 0) {
            key ^= ep_file[board.en_passant % 8];
        }
        if (!board.white_to_move) {
            key ^= turn;
        }
        return key;
    }
};

enum class Bound : uint8_t { Exact, Lower, Upper };

struct TTEntry {
    uint64_t key = 0;
    int depth = -1;
    int score = 0;
    Bound bound = Bound::Exact;
    Move move{};
    uint16_t generation = 0;
};

class Timeout final : public std::exception {};

class Engine {
public:
    explicit Engine(std::size_t hash_megabytes = 64) {
        resize_table(hash_megabytes);
    }

    void resize_table(std::size_t megabytes) {
        std::size_t bytes = std::max<std::size_t>(1, megabytes) * 1024 * 1024;
        std::size_t entries = std::max<std::size_t>(1024, bytes / sizeof(TTEntry));
        std::size_t power = 1;
        while (power * 2 <= entries) {
            power *= 2;
        }
        table_.assign(power, TTEntry{});
    }

    void clear() {
        std::fill(table_.begin(), table_.end(), TTEntry{});
        history_ = {};
        killers_ = {};
        countermoves_ = {};
    }

    struct Result {
        Move move{};
        int score = 0;
        int depth = 0;
        uint64_t nodes = 0;
        long long elapsed_ms = 0;
        std::vector<Move> pv;
    };

    Result search(
        const Board& position,
        int max_depth,
        int move_time_ms,
        const std::vector<uint64_t>& game_history = {}
    ) {
        nodes_ = 0;
        ++generation_;
        search_history_ = game_history;
        deadline_ = std::chrono::steady_clock::now()
            + std::chrono::milliseconds(std::max(1, move_time_ms));
        auto started = std::chrono::steady_clock::now();
        Result result;
        auto legal = position.legal_moves();
        if (legal.empty()) {
            return result;
        }
        result.move = legal.front();
        int previous = 0;

        for (int depth = 1; depth <= max_depth; ++depth) {
            int window = depth >= 4 ? 40 : INF;
            int alpha = std::max(-INF, previous - window);
            int beta = std::min(INF, previous + window);
            try {
                while (true) {
                    auto [score, move] = root(position, depth, alpha, beta);
                    if (score <= alpha && alpha > -INF) {
                        window *= 2;
                        alpha = std::max(-INF, score - window);
                        continue;
                    }
                    if (score >= beta && beta < INF) {
                        window *= 2;
                        beta = std::min(INF, score + window);
                        continue;
                    }
                    result.move = move;
                    result.score = score;
                    result.depth = depth;
                    previous = score;
                    break;
                }
            } catch (const Timeout&) {
                break;
            }
            if (std::abs(result.score) > MATE - MAX_PLY) {
                break;
            }
        }
        result.nodes = nodes_;
        result.elapsed_ms = std::chrono::duration_cast<std::chrono::milliseconds>(
            std::chrono::steady_clock::now() - started
        ).count();
        result.pv = principal_variation(position, result.depth);
        return result;
    }

private:
    std::vector<TTEntry> table_;
    Zobrist zobrist_;
    std::array<std::array<Move, 2>, MAX_PLY> killers_{};
    std::array<std::array<int, 64>, 128> history_{};
    std::array<std::array<Move, 64>, 128> countermoves_{};
    std::vector<uint64_t> search_history_;
    uint64_t nodes_ = 0;
    uint16_t generation_ = 0;
    std::chrono::steady_clock::time_point deadline_{};

    void check_time() {
        if ((nodes_ & 2047ULL) == 0
            && std::chrono::steady_clock::now() >= deadline_) {
            throw Timeout{};
        }
    }

    int evaluate(const Board& board) const {
        int score = mwahaha_evaluate(board.squares.data());
        return board.white_to_move ? score : -score;
    }

    int capture_value(const Board& board, const Move& move) const {
        char victim = board.squares[move.to];
        if (move.flags & EN_PASSANT) {
            victim = 'p';
        }
        int value = victim == '.' ? 0 : PIECE_VALUES[static_cast<int>(victim)];
        if (move.promotion != '\0') {
            value += PIECE_VALUES[static_cast<int>(move.promotion)] - 100;
        }
        return value;
    }

    bool quiet(const Board& board, const Move& move) const {
        return board.squares[move.to] == '.'
            && !(move.flags & EN_PASSANT) && move.promotion == '\0';
    }

    void update_history(char piece, int target, int bonus) {
        constexpr int HISTORY_LIMIT = 16'384;
        bonus = std::clamp(bonus, -HISTORY_LIMIT, HISTORY_LIMIT);
        int& value = history_[static_cast<int>(piece)][target];
        value += bonus - value * std::abs(bonus) / HISTORY_LIMIT;
    }

    void order_moves(
        const Board& board,
        std::vector<Move>& moves,
        const Move& tt_move,
        int ply,
        const Move& counter_move = Move{}
    ) {
        auto score = [&](const Move& move) {
            if (tt_move.valid() && move == tt_move) {
                return 10'000'000;
            }
            char piece = board.squares[move.from];
            char victim = board.squares[move.to];
            int value = 0;
            if (victim != '.' || (move.flags & EN_PASSANT)) {
                value += 1'000'000 + 16 * capture_value(board, move)
                    - PIECE_VALUES[static_cast<int>(piece)];
            }
            if (move.promotion != '\0') {
                value += 900'000 + PIECE_VALUES[static_cast<int>(move.promotion)];
            }
            if (ply < MAX_PLY) {
                if (move == killers_[ply][0]) value += 700'000;
                if (move == killers_[ply][1]) value += 690'000;
            }
            if (counter_move.valid() && move == counter_move) {
                value += 680'000;
            }
            value += history_[static_cast<int>(piece)][move.to];
            if (move.flags & CASTLING) value += 25'000;
            return value;
        };
        std::stable_sort(
            moves.begin(),
            moves.end(),
            [&](const Move& left, const Move& right) {
                return score(left) > score(right);
            }
        );
    }

    TTEntry* probe(uint64_t key) {
        TTEntry& entry = table_[key & (table_.size() - 1)];
        return entry.key == key ? &entry : nullptr;
    }

    static int score_to_table(int score, int ply) {
        if (score > MATE - MAX_PLY) return score + ply;
        if (score < -MATE + MAX_PLY) return score - ply;
        return score;
    }

    static int score_from_table(int score, int ply) {
        if (score > MATE - MAX_PLY) return score - ply;
        if (score < -MATE + MAX_PLY) return score + ply;
        return score;
    }

    void store(
        uint64_t key,
        int depth,
        int score,
        Bound bound,
        const Move& move,
        int ply
    ) {
        TTEntry& entry = table_[key & (table_.size() - 1)];
        bool same_position = entry.key == key;
        bool stale = entry.generation != generation_;
        if (
            (same_position && depth >= entry.depth)
            || (!same_position && (stale || depth + 2 >= entry.depth))
        ) {
            entry = {
                key,
                depth,
                score_to_table(score, ply),
                bound,
                move,
                generation_
            };
        }
    }

    std::pair<int, Move> root(
        const Board& board,
        int depth,
        int alpha,
        int beta
    ) {
        check_time();
        uint64_t key = zobrist_.hash(board);
        TTEntry* entry = probe(key);
        Move tt_move = entry == nullptr ? Move{} : entry->move;
        auto moves = board.legal_moves();
        order_moves(board, moves, tt_move, 0);
        Move best = moves.front();
        int best_score = -INF;
        int original_alpha = alpha;

        for (std::size_t index = 0; index < moves.size(); ++index) {
            Board child = board;
            child.make_move(moves[index]);
            int score;
            if (index == 0) {
                score = -negamax(
                    child, depth - 1, -beta, -alpha, 1, true, moves[index]
                );
            } else {
                score = -negamax(
                    child,
                    depth - 1,
                    -alpha - 1,
                    -alpha,
                    1,
                    true,
                    moves[index]
                );
                if (score > alpha && score < beta) {
                    score = -negamax(
                        child, depth - 1, -beta, -alpha, 1, true, moves[index]
                    );
                }
            }
            if (score > best_score) {
                best_score = score;
                best = moves[index];
            }
            alpha = std::max(alpha, score);
            if (alpha >= beta) {
                break;
            }
        }
        Bound bound = best_score <= original_alpha
            ? Bound::Upper
            : (best_score >= beta ? Bound::Lower : Bound::Exact);
        store(key, depth, best_score, bound, best, 0);
        return {best_score, best};
    }

    int negamax(
        const Board& board,
        int depth,
        int alpha,
        int beta,
        int ply,
        bool allow_null,
        const Move& previous_move
    ) {
        ++nodes_;
        check_time();
        bool in_check = board.in_check();
        if (depth <= 0) {
            return quiescence(board, alpha, beta, ply, 0);
        }
        if (ply >= MAX_PLY - 1) {
            return evaluate(board);
        }
        alpha = std::max(alpha, -MATE + ply);
        beta = std::min(beta, MATE - ply - 1);
        if (alpha >= beta) {
            return alpha;
        }

        uint64_t key = zobrist_.hash(board);
        int prior_visits = static_cast<int>(
            std::count(search_history_.begin(), search_history_.end(), key)
        );
        if (prior_visits >= 2 || board.halfmove >= 100) {
            return 0;
        }
        struct HistoryGuard {
            std::vector<uint64_t>& history;
            explicit HistoryGuard(std::vector<uint64_t>& values, uint64_t key)
                : history(values) {
                history.push_back(key);
            }
            ~HistoryGuard() {
                history.pop_back();
            }
        } history_guard(search_history_, key);

        TTEntry* entry = probe(key);
        if (entry != nullptr && entry->depth >= depth) {
            int table_score = score_from_table(entry->score, ply);
            if (entry->bound == Bound::Exact) return table_score;
            if (entry->bound == Bound::Lower && table_score >= beta) {
                return table_score;
            }
            if (entry->bound == Bound::Upper && table_score <= alpha) {
                return table_score;
            }
        }
        int static_eval = in_check ? -INF : evaluate(board);
        if (
            !in_check
            && depth <= 3
            && beta - alpha == 1
            && std::abs(beta) < MATE - MAX_PLY
            && static_eval - 85 * depth >= beta
        ) {
            return static_eval;
        }
        if (
            !in_check
            && depth == 1
            && beta - alpha == 1
            && std::abs(alpha) < MATE - MAX_PLY
            && static_eval + 240 < alpha
        ) {
            int razor_score = quiescence(board, alpha, beta, ply, 0);
            if (razor_score < alpha) {
                return razor_score;
            }
        }
        if (allow_null && depth >= 3 && !in_check && has_non_pawn_material(board)) {
            Board null_board = board;
            null_board.white_to_move = !null_board.white_to_move;
            null_board.en_passant = -1;
            ++null_board.halfmove;
            int reduction = 2 + depth / 5;
            int score = -negamax(
                null_board,
                depth - 1 - reduction,
                -beta,
                -beta + 1,
                ply + 1,
                false,
                Move{}
            );
            if (score >= beta) {
                return score;
            }
        }

        auto moves = board.legal_moves();
        if (moves.empty()) {
            return in_check ? -MATE + ply : 0;
        }
        Move tt_move = entry == nullptr ? Move{} : entry->move;
        Move counter_move{};
        if (previous_move.valid()) {
            char previous_piece = board.squares[previous_move.to];
            if (previous_piece != '.') {
                counter_move = countermoves_[
                    static_cast<int>(previous_piece)
                ][previous_move.to];
            }
        }
        order_moves(board, moves, tt_move, ply, counter_move);
        int original_alpha = alpha;
        int best_score = -INF;
        Move best{};
        int static_score = depth <= 2 && !in_check ? static_eval : -INF;
        std::vector<Move> quiets_tried;

        for (std::size_t index = 0; index < moves.size(); ++index) {
            const Move& move = moves[index];
            bool is_quiet = quiet(board, move);
            Board child = board;
            child.make_move(move);
            bool gives_check = child.in_check();
            if (
                depth <= 2
                && index >= static_cast<std::size_t>(8 + depth * 4)
                && is_quiet
                && !in_check
                && !gives_check
                && static_eval + 110 * depth <= alpha
            ) {
                continue;
            }
            if (depth == 1 && index > 0 && is_quiet && !gives_check
                && static_score + 140 <= alpha) {
                continue;
            }
            int next_depth = depth - 1;
            if (gives_check && depth <= 2) {
                ++next_depth;
            }
            int reduction = 0;
            if (
                depth >= 3
                && index >= 3
                && is_quiet
                && !in_check
                && !gives_check
            ) {
                reduction = static_cast<int>(
                    0.75
                    + std::log(static_cast<double>(depth))
                    * std::log(static_cast<double>(index + 1))
                    / 2.15
                );
                int history_score = history_[
                    static_cast<int>(board.squares[move.from])
                ][move.to];
                if (
                    history_score > 4'000
                    || move == killers_[ply][0]
                    || move == counter_move
                ) {
                    --reduction;
                }
                reduction = std::clamp(reduction, 1, std::max(1, next_depth - 1));
            }

            int score;
            if (index == 0) {
                score = -negamax(
                    child, next_depth, -beta, -alpha, ply + 1, true, move
                );
            } else {
                score = -negamax(
                    child,
                    std::max(0, next_depth - reduction),
                    -alpha - 1,
                    -alpha,
                    ply + 1,
                    true,
                    move
                );
                if (reduction != 0 && score > alpha) {
                    score = -negamax(
                        child,
                        next_depth,
                        -alpha - 1,
                        -alpha,
                        ply + 1,
                        true,
                        move
                    );
                }
                if (score > alpha && score < beta) {
                    score = -negamax(
                        child, next_depth, -beta, -alpha, ply + 1, true, move
                    );
                }
            }
            if (score > best_score) {
                best_score = score;
                best = move;
            }
            if (score > alpha) {
                alpha = score;
            }
            if (alpha >= beta) {
                if (is_quiet) {
                    int bonus = std::min(16'384, depth * depth * 32);
                    update_history(board.squares[move.from], move.to, bonus);
                    for (const Move& previous : quiets_tried) {
                        update_history(
                            board.squares[previous.from],
                            previous.to,
                            -bonus / 2
                        );
                    }
                    killers_[ply][1] = killers_[ply][0];
                    killers_[ply][0] = move;
                    if (previous_move.valid()) {
                        char previous_piece = board.squares[previous_move.to];
                        if (previous_piece != '.') {
                            countermoves_[
                                static_cast<int>(previous_piece)
                            ][previous_move.to] = move;
                        }
                    }
                }
                break;
            }
            if (is_quiet) {
                quiets_tried.push_back(move);
            }
        }
        Bound bound = best_score <= original_alpha
            ? Bound::Upper
            : (best_score >= beta ? Bound::Lower : Bound::Exact);
        store(key, depth, best_score, bound, best, ply);
        return best_score;
    }

    int quiescence(
        const Board& board,
        int alpha,
        int beta,
        int ply,
        int qply
    ) {
        ++nodes_;
        check_time();
        bool in_check = board.in_check();
        int stand_pat = evaluate(board);
        if (!in_check) {
            if (stand_pat >= beta) {
                return stand_pat;
            }
            alpha = std::max(alpha, stand_pat);
            if (qply >= 10) {
                return stand_pat;
            }
        }
        auto moves = board.legal_moves(!in_check);
        if (moves.empty()) {
            return in_check ? -MATE + ply : alpha;
        }
        order_moves(board, moves, Move{}, ply);
        for (const Move& move : moves) {
            if (!in_check && move.promotion == '\0'
                && stand_pat + capture_value(board, move) + 140 < alpha) {
                continue;
            }
            Board child = board;
            child.make_move(move);
            int score = -quiescence(child, -beta, -alpha, ply + 1, qply + 1);
            if (score >= beta) {
                return score;
            }
            alpha = std::max(alpha, score);
        }
        return alpha;
    }

    bool has_non_pawn_material(const Board& board) const {
        for (char piece : board.squares) {
            if (piece != '.' && is_white(piece) == board.white_to_move) {
                char type = static_cast<char>(std::tolower(piece));
                if (type != 'p' && type != 'k') {
                    return true;
                }
            }
        }
        return false;
    }

    std::vector<Move> principal_variation(Board board, int depth) {
        std::vector<Move> pv;
        for (int index = 0; index < depth; ++index) {
            TTEntry* entry = probe(zobrist_.hash(board));
            if (entry == nullptr || !entry->move.valid()) {
                break;
            }
            auto legal = board.legal_moves();
            auto found = std::find(legal.begin(), legal.end(), entry->move);
            if (found == legal.end()) {
                break;
            }
            pv.push_back(*found);
            board.make_move(*found);
        }
        return pv;
    }
};

uint64_t perft(const Board& board, int depth) {
    if (depth == 0) {
        return 1;
    }
    uint64_t nodes = 0;
    for (const Move& move : board.legal_moves()) {
        Board child = board;
        child.make_move(move);
        nodes += perft(child, depth - 1);
    }
    return nodes;
}

std::vector<std::string> split(const std::string& input) {
    std::istringstream stream(input);
    std::vector<std::string> tokens;
    std::string token;
    while (stream >> token) {
        tokens.push_back(token);
    }
    return tokens;
}

void parse_position(
    Board& board,
    const std::string& command,
    std::vector<uint64_t>& history,
    const Zobrist& hasher
) {
    auto tokens = split(command);
    if (tokens.size() < 2) {
        throw std::invalid_argument("incomplete position command");
    }
    std::size_t moves_index = tokens.size();
    if (tokens[1] == "startpos") {
        board = Board::starting();
        auto found = std::find(tokens.begin(), tokens.end(), "moves");
        if (found != tokens.end()) {
            moves_index = static_cast<std::size_t>(
                std::distance(tokens.begin(), found) + 1
            );
        }
    } else if (tokens[1] == "fen") {
        auto found = std::find(tokens.begin(), tokens.end(), "moves");
        std::size_t fen_end = found == tokens.end()
            ? tokens.size()
            : static_cast<std::size_t>(std::distance(tokens.begin(), found));
        std::ostringstream fen;
        for (std::size_t index = 2; index < fen_end; ++index) {
            if (index != 2) fen << ' ';
            fen << tokens[index];
        }
        board = Board::from_fen(fen.str());
        if (found != tokens.end()) {
            moves_index = fen_end + 1;
        }
    } else {
        throw std::invalid_argument("position requires startpos or fen");
    }
    history.clear();
    history.push_back(hasher.hash(board));
    for (std::size_t index = moves_index; index < tokens.size(); ++index) {
        Move move = board.find_move(tokens[index]);
        board.make_move(move);
        history.push_back(hasher.hash(board));
    }
}

int option_value(const std::vector<std::string>& tokens, const std::string& name) {
    auto found = std::find(tokens.begin(), tokens.end(), name);
    if (found == tokens.end() || found + 1 == tokens.end()) {
        return -1;
    }
    return std::stoi(*(found + 1));
}

int uci_loop() {
    Board board = Board::starting();
    Engine engine;
    Zobrist history_hasher;
    std::vector<uint64_t> game_history{history_hasher.hash(board)};
    int overhead = 10;
    std::string line;
    while (std::getline(std::cin, line)) {
        try {
            if (line == "uci") {
                std::cout << "id name Mwahaha Native Engine 2.0\n";
                std::cout << "id author Mohammed Nabid\n";
                std::cout << "option name Hash type spin default 64 min 1 max 2048\n";
                std::cout << "option name Move Overhead type spin default 10 min 0 max 5000\n";
                std::cout << "uciok\n" << std::flush;
            } else if (line == "isready") {
                std::cout << "readyok\n" << std::flush;
            } else if (line == "ucinewgame") {
                board = Board::starting();
                game_history = {history_hasher.hash(board)};
                engine.clear();
            } else if (line.rfind("setoption name Hash value ", 0) == 0) {
                engine.resize_table(static_cast<std::size_t>(
                    std::max(1, std::stoi(line.substr(26)))
                ));
            } else if (
                line.rfind("setoption name Move Overhead value ", 0) == 0
            ) {
                overhead = std::max(0, std::stoi(line.substr(39)));
            } else if (line.rfind("position ", 0) == 0) {
                parse_position(board, line, game_history, history_hasher);
            } else if (line.rfind("go", 0) == 0) {
                auto tokens = split(line);
                int requested_depth = option_value(tokens, "depth");
                int move_time = option_value(tokens, "movetime");
                if (move_time < 0) {
                    std::string clock_name = board.white_to_move ? "wtime" : "btime";
                    std::string increment_name = board.white_to_move ? "winc" : "binc";
                    int remaining = option_value(tokens, clock_name);
                    int increment = std::max(0, option_value(tokens, increment_name));
                    int moves_to_go = option_value(tokens, "movestogo");
                    if (moves_to_go < 1) moves_to_go = 30;
                    move_time = remaining < 0
                        ? 1000
                        : remaining / std::max(8, moves_to_go) + increment * 3 / 4;
                }
                move_time = std::max(1, move_time - overhead);
                int depth = requested_depth < 1 ? 64 : requested_depth;
                if (requested_depth > 0 && option_value(tokens, "movetime") < 0) {
                    move_time = 3'600'000;
                }
                Engine::Result result = engine.search(
                    board,
                    depth,
                    move_time,
                    game_history
                );
                uint64_t nps = result.nodes * 1000
                    / static_cast<uint64_t>(std::max<long long>(1, result.elapsed_ms));
                std::cout << "info depth " << result.depth
                    << " score cp " << result.score
                    << " nodes " << result.nodes
                    << " nps " << nps
                    << " time " << result.elapsed_ms
                    << " pv";
                for (const Move& move : result.pv) {
                    std::cout << ' ' << move.uci();
                }
                std::cout << "\nbestmove " << result.move.uci()
                    << '\n' << std::flush;
            } else if (line == "quit") {
                break;
            }
        } catch (const std::exception& error) {
            std::cout << "info string error: " << error.what() << '\n' << std::flush;
        }
    }
    return 0;
}

}  // namespace

int main(int argc, char** argv) {
    if (argc == 3 && std::string(argv[1]) == "--perft") {
        int depth = std::stoi(argv[2]);
        auto started = std::chrono::steady_clock::now();
        uint64_t nodes = perft(Board::starting(), depth);
        auto elapsed = std::chrono::duration_cast<std::chrono::milliseconds>(
            std::chrono::steady_clock::now() - started
        ).count();
        std::cout << "depth " << depth << ": " << nodes
            << " nodes in " << elapsed << " ms\n";
        return 0;
    }
    if (argc >= 4 && std::string(argv[1]) == "--perft-fen") {
        int depth = std::stoi(argv[2]);
        std::ostringstream fen;
        for (int index = 3; index < argc; ++index) {
            if (index != 3) fen << ' ';
            fen << argv[index];
        }
        auto started = std::chrono::steady_clock::now();
        uint64_t nodes = perft(Board::from_fen(fen.str()), depth);
        auto elapsed = std::chrono::duration_cast<std::chrono::milliseconds>(
            std::chrono::steady_clock::now() - started
        ).count();
        std::cout << "depth " << depth << ": " << nodes
            << " nodes in " << elapsed << " ms\n";
        return 0;
    }
    return uci_loop();
}
