#include <algorithm>
#include <array>
#include <atomic>
#include <bit>
#include <chrono>
#include <cctype>
#include <cstddef>
#include <cmath>
#include <cstdint>
#include <cstdlib>
#include <iostream>
#include <limits>
#include <memory>
#include <mutex>
#include <sstream>
#include <stdexcept>
#include <string>
#include <thread>
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
constexpr uint64_t FILE_A = 0x0101010101010101ULL;
constexpr uint64_t FILE_H = 0x8080808080808080ULL;

constexpr uint64_t square_bit(int square) {
    return 1ULL << square;
}

constexpr std::array<uint64_t, 64> build_knight_attacks() {
    std::array<uint64_t, 64> attacks{};
    constexpr int offsets[8][2] = {
        {-2, -1}, {-2, 1}, {-1, -2}, {-1, 2},
        {1, -2}, {1, 2}, {2, -1}, {2, 1}
    };
    for (int square = 0; square < 64; ++square) {
        int row = square / 8;
        int column = square % 8;
        for (const auto& offset : offsets) {
            int target_row = row + offset[0];
            int target_column = column + offset[1];
            if (target_row >= 0 && target_row < 8
                && target_column >= 0 && target_column < 8) {
                attacks[square] |= square_bit(target_row * 8 + target_column);
            }
        }
    }
    return attacks;
}

constexpr std::array<uint64_t, 64> build_king_attacks() {
    std::array<uint64_t, 64> attacks{};
    for (int square = 0; square < 64; ++square) {
        int row = square / 8;
        int column = square % 8;
        for (int row_delta = -1; row_delta <= 1; ++row_delta) {
            for (int column_delta = -1; column_delta <= 1; ++column_delta) {
                if (row_delta == 0 && column_delta == 0) {
                    continue;
                }
                int target_row = row + row_delta;
                int target_column = column + column_delta;
                if (target_row >= 0 && target_row < 8
                    && target_column >= 0 && target_column < 8) {
                    attacks[square] |= square_bit(
                        target_row * 8 + target_column
                    );
                }
            }
        }
    }
    return attacks;
}

constexpr auto KNIGHT_ATTACKS = build_knight_attacks();
constexpr auto KING_ATTACKS = build_king_attacks();

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

uint64_t splitmix64(uint64_t& state) {
    uint64_t value = (state += 0x9e3779b97f4a7c15ULL);
    value = (value ^ (value >> 30)) * 0xbf58476d1ce4e5b9ULL;
    value = (value ^ (value >> 27)) * 0x94d049bb133111ebULL;
    return value ^ (value >> 31);
}

struct Board;

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

    uint64_t hash(const Board& board) const;
};

extern const Zobrist ZOBRIST;

struct Move {
    int8_t from = -1;
    int8_t to = -1;
    char promotion = '\0';
    uint8_t flags = 0;

    constexpr Move() = default;

    constexpr Move(int source, int target, char promoted = '\0', int attributes = 0)
        : from(static_cast<int8_t>(source)),
          to(static_cast<int8_t>(target)),
          promotion(promoted),
          flags(static_cast<uint8_t>(attributes)) {}

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

static_assert(sizeof(Move) == 4);

template <typename T, std::size_t Capacity>
class FixedList {
public:
    using iterator = typename std::array<T, Capacity>::iterator;
    using const_iterator = typename std::array<T, Capacity>::const_iterator;

    constexpr bool empty() const { return size_ == 0; }
    constexpr std::size_t size() const { return size_; }
    constexpr std::size_t capacity() const { return Capacity; }
    constexpr T& front() { return values_[0]; }
    constexpr const T& front() const { return values_[0]; }
    constexpr T& operator[](std::size_t index) { return values_[index]; }
    constexpr const T& operator[](std::size_t index) const {
        return values_[index];
    }
    constexpr iterator begin() { return values_.begin(); }
    constexpr const_iterator begin() const { return values_.begin(); }
    constexpr iterator end() {
        return values_.begin() + static_cast<std::ptrdiff_t>(size_);
    }
    constexpr const_iterator end() const {
        return values_.begin() + static_cast<std::ptrdiff_t>(size_);
    }

    constexpr void clear() { size_ = 0; }

    constexpr void push_back(const T& value) {
        if (size_ >= Capacity) [[unlikely]] {
            throw std::overflow_error("fixed list capacity exceeded");
        }
        values_[size_++] = value;
    }

private:
    std::array<T, Capacity> values_{};
    std::size_t size_ = 0;
};

using MoveList = FixedList<Move, 256>;

struct Board {
    struct UndoState {
        char moved = '.';
        char captured = '.';
        int captured_square = -1;
        int castling = 0;
        int en_passant = -1;
        int halfmove = 0;
        int fullmove = 1;
        uint64_t key = 0;
    };

    std::array<char, 64> squares{};
    std::array<uint64_t, 12> piece_boards{};
    std::array<uint64_t, 2> color_boards{};
    uint64_t occupied = 0;
    bool white_to_move = true;
    int castling = WHITE_KING_SIDE | WHITE_QUEEN_SIDE
        | BLACK_KING_SIDE | BLACK_QUEEN_SIDE;
    int en_passant = -1;
    int halfmove = 0;
    int fullmove = 1;
    uint64_t key = 0;

    Board() {
        squares.fill('.');
    }

    static int color_index(bool white) {
        return white ? 0 : 1;
    }

    void place_piece(char piece, int square) {
        uint64_t bit = square_bit(square);
        squares[square] = piece;
        piece_boards[Zobrist::piece_index(piece)] |= bit;
        color_boards[color_index(is_white(piece))] |= bit;
        occupied |= bit;
    }

    char remove_piece(int square) {
        char piece = squares[square];
        if (piece == '.') {
            return piece;
        }
        uint64_t bit = square_bit(square);
        squares[square] = '.';
        piece_boards[Zobrist::piece_index(piece)] &= ~bit;
        color_boards[color_index(is_white(piece))] &= ~bit;
        occupied &= ~bit;
        return piece;
    }

    void rebuild_bitboards() {
        piece_boards.fill(0);
        color_boards.fill(0);
        occupied = 0;
        for (int square = 0; square < 64; ++square) {
            char piece = squares[square];
            if (piece != '.') {
                uint64_t bit = square_bit(square);
                piece_boards[Zobrist::piece_index(piece)] |= bit;
                color_boards[color_index(is_white(piece))] |= bit;
                occupied |= bit;
            }
        }
    }

    bool bitboards_valid() const {
        Board rebuilt = *this;
        rebuilt.rebuild_bitboards();
        return rebuilt.piece_boards == piece_boards
            && rebuilt.color_boards == color_boards
            && rebuilt.occupied == occupied;
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
        board.rebuild_bitboards();
        board.key = ZOBRIST.hash(board);
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

    uint64_t sliding_attacks(int from, int start, int stop) const {
        constexpr int directions[8][2] = {
            {-1, -1}, {-1, 1}, {1, -1}, {1, 1},
            {-1, 0}, {1, 0}, {0, -1}, {0, 1}
        };
        uint64_t attacks = 0;
        int row = from / 8;
        int column = from % 8;
        for (int index = start; index < stop; ++index) {
            int target_row = row + directions[index][0];
            int target_column = column + directions[index][1];
            while (target_row >= 0 && target_row < 8
                && target_column >= 0 && target_column < 8) {
                int target = target_row * 8 + target_column;
                uint64_t bit = square_bit(target);
                attacks |= bit;
                if (occupied & bit) {
                    break;
                }
                target_row += directions[index][0];
                target_column += directions[index][1];
            }
        }
        return attacks;
    }

    uint64_t bishop_attacks(int from) const {
        return sliding_attacks(from, 0, 4);
    }

    uint64_t rook_attacks(int from) const {
        return sliding_attacks(from, 4, 8);
    }

    uint64_t pawn_attacks(bool by_white) const {
        uint64_t pawns = piece_boards[
            Zobrist::piece_index(by_white ? 'P' : 'p')
        ];
        if (by_white) {
            return ((pawns & ~FILE_A) >> 9) | ((pawns & ~FILE_H) >> 7);
        }
        return ((pawns & ~FILE_H) << 9) | ((pawns & ~FILE_A) << 7);
    }

    bool attacked(int target, bool by_white) const {
        uint64_t target_bit = square_bit(target);
        if (pawn_attacks(by_white) & target_bit) {
            return true;
        }
        uint64_t knights = piece_boards[
            Zobrist::piece_index(by_white ? 'N' : 'n')
        ];
        if (KNIGHT_ATTACKS[target] & knights) {
            return true;
        }
        uint64_t kings = piece_boards[
            Zobrist::piece_index(by_white ? 'K' : 'k')
        ];
        if (KING_ATTACKS[target] & kings) {
            return true;
        }
        uint64_t bishops = piece_boards[
            Zobrist::piece_index(by_white ? 'B' : 'b')
        ];
        uint64_t rooks = piece_boards[
            Zobrist::piece_index(by_white ? 'R' : 'r')
        ];
        uint64_t queens = piece_boards[
            Zobrist::piece_index(by_white ? 'Q' : 'q')
        ];
        return (bishop_attacks(target) & (bishops | queens))
            || (rook_attacks(target) & (rooks | queens));
    }

    int king_square(bool white) const {
        uint64_t king = piece_boards[
            Zobrist::piece_index(white ? 'K' : 'k')
        ];
        return king == 0 ? -1 : static_cast<int>(std::countr_zero(king));
    }

    bool in_check(bool white) const {
        int king = king_square(white);
        return king >= 0 && attacked(king, !white);
    }

    bool in_check() const {
        return in_check(white_to_move);
    }

    template <typename Moves>
    void add_promotions(Moves& moves, int from, int to, int flags) const {
        for (char promotion : {'q', 'r', 'b', 'n'}) {
            moves.push_back({from, to, promotion, flags});
        }
    }

    MoveList pseudo_moves(bool captures_only = false) const {
        MoveList moves;
        uint64_t own = color_boards[color_index(white_to_move)];
        uint64_t enemy = color_boards[color_index(!white_to_move)];
        uint64_t remaining = own;
        while (remaining != 0) {
            int from = static_cast<int>(std::countr_zero(remaining));
            remaining &= remaining - 1;
            char piece = squares[from];
            char type = static_cast<char>(std::tolower(piece));
            int row = from / 8;
            int column = from % 8;
            if (type == 'p') {
                int direction = white_to_move ? -1 : 1;
                int promotion_row = white_to_move ? 0 : 7;
                int start_row = white_to_move ? 6 : 1;
                int next_row = row + direction;
                if (next_row >= 0 && next_row < 8) {
                    int one = next_row * 8 + column;
                    if (squares[one] == '.') {
                        if (next_row == promotion_row) {
                            add_promotions(moves, from, one, 0);
                        } else if (!captures_only) {
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
                uint64_t targets = (type == 'n'
                    ? KNIGHT_ATTACKS[from]
                    : KING_ATTACKS[from]) & ~own;
                if (captures_only) {
                    targets &= enemy;
                }
                while (targets != 0) {
                    int to = static_cast<int>(std::countr_zero(targets));
                    targets &= targets - 1;
                    moves.push_back({from, to, '\0', 0});
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
                uint64_t targets = type == 'b'
                    ? bishop_attacks(from)
                    : (type == 'r'
                        ? rook_attacks(from)
                        : bishop_attacks(from) | rook_attacks(from));
                targets &= ~own;
                if (captures_only) {
                    targets &= enemy;
                }
                while (targets != 0) {
                    int to = static_cast<int>(std::countr_zero(targets));
                    targets &= targets - 1;
                    moves.push_back({from, to, '\0', 0});
                }
            }
        }
        return moves;
    }

    UndoState make_move(const Move& move) {
        char piece = squares[move.from];
        bool moving_white = is_white(piece);
        char captured = squares[move.to];
        int captured_square = move.to;
        UndoState undo{
            piece,
            captured,
            captured_square,
            castling,
            en_passant,
            halfmove,
            fullmove,
            key
        };
        if (move.flags & EN_PASSANT) {
            captured_square = move.to + (moving_white ? 8 : -8);
            captured = squares[captured_square];
            undo.captured = captured;
            undo.captured_square = captured_square;
        }

        key ^= ZOBRIST.castling[castling];
        if (en_passant >= 0) {
            key ^= ZOBRIST.ep_file[en_passant % 8];
        }
        key ^= ZOBRIST.turn;
        key ^= ZOBRIST.pieces[Zobrist::piece_index(piece)][move.from];
        if (captured != '.') {
            key ^= ZOBRIST.pieces[
                Zobrist::piece_index(captured)
            ][captured_square];
        }

        remove_piece(move.from);
        if (captured != '.') {
            remove_piece(captured_square);
        }
        char placed = move.promotion == '\0'
            ? piece
            : static_cast<char>(
                moving_white ? std::toupper(move.promotion) : move.promotion
            );
        place_piece(placed, move.to);
        key ^= ZOBRIST.pieces[Zobrist::piece_index(placed)][move.to];

        if (move.flags & CASTLING) {
            if (move.to == 62) {
                key ^= ZOBRIST.pieces[Zobrist::piece_index('R')][63];
                key ^= ZOBRIST.pieces[Zobrist::piece_index('R')][61];
                remove_piece(63);
                place_piece('R', 61);
            } else if (move.to == 58) {
                key ^= ZOBRIST.pieces[Zobrist::piece_index('R')][56];
                key ^= ZOBRIST.pieces[Zobrist::piece_index('R')][59];
                remove_piece(56);
                place_piece('R', 59);
            } else if (move.to == 6) {
                key ^= ZOBRIST.pieces[Zobrist::piece_index('r')][7];
                key ^= ZOBRIST.pieces[Zobrist::piece_index('r')][5];
                remove_piece(7);
                place_piece('r', 5);
            } else if (move.to == 2) {
                key ^= ZOBRIST.pieces[Zobrist::piece_index('r')][0];
                key ^= ZOBRIST.pieces[Zobrist::piece_index('r')][3];
                remove_piece(0);
                place_piece('r', 3);
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
        key ^= ZOBRIST.castling[castling];
        if (en_passant >= 0) {
            key ^= ZOBRIST.ep_file[en_passant % 8];
        }
        return undo;
    }

    void unmake_move(const Move& move, const UndoState& undo) {
        white_to_move = !white_to_move;
        castling = undo.castling;
        en_passant = undo.en_passant;
        halfmove = undo.halfmove;
        fullmove = undo.fullmove;
        key = undo.key;

        if (move.flags & CASTLING) {
            if (move.to == 62) {
                remove_piece(61);
                place_piece('R', 63);
            } else if (move.to == 58) {
                remove_piece(59);
                place_piece('R', 56);
            } else if (move.to == 6) {
                remove_piece(5);
                place_piece('r', 7);
            } else if (move.to == 2) {
                remove_piece(3);
                place_piece('r', 0);
            }
        }

        remove_piece(move.to);
        place_piece(undo.moved, move.from);
        if (undo.captured != '.') {
            place_piece(undo.captured, undo.captured_square);
        }
    }

    MoveList legal_moves_in_place(bool captures_only = false) {
        MoveList legal;
        bool moving_white = white_to_move;
        for (const Move& move : pseudo_moves(captures_only)) {
            UndoState undo = make_move(move);
            if (!in_check(moving_white)) {
                legal.push_back(move);
            }
            unmake_move(move, undo);
        }
        return legal;
    }

    std::vector<Move> legal_moves(bool captures_only = false) const {
        Board position = *this;
        MoveList legal = position.legal_moves_in_place(captures_only);
        return {legal.begin(), legal.end()};
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

class ScopedMove {
public:
    ScopedMove(Board& board, const Move& move)
        : board_(board), move_(move), undo_(board.make_move(move)) {}

    ScopedMove(const ScopedMove&) = delete;
    ScopedMove& operator=(const ScopedMove&) = delete;

    ~ScopedMove() {
        board_.unmake_move(move_, undo_);
    }

private:
    Board& board_;
    Move move_;
    Board::UndoState undo_;
};

uint64_t Zobrist::hash(const Board& board) const {
    uint64_t key = 0;
    for (int piece = 0; piece < 12; ++piece) {
        uint64_t remaining = board.piece_boards[piece];
        while (remaining != 0) {
            int square = static_cast<int>(std::countr_zero(remaining));
            key ^= pieces[piece][square];
            remaining &= remaining - 1;
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

const Zobrist ZOBRIST{};

enum class Bound : uint8_t { Exact, Lower, Upper };

struct TTEntry {
    uint64_t key = 0;
    int depth = -1;
    int score = 0;
    int static_eval = INF;
    Bound bound = Bound::Exact;
    Move move{};
    uint16_t generation = 0;
};

struct TTCluster {
    static constexpr std::size_t SIZE = 3;
    std::array<TTEntry, SIZE> entries{};
};

class Timeout final : public std::exception {};

class Engine {
public:
    explicit Engine(std::size_t hash_megabytes = 64) {
        resize_table(hash_megabytes);
    }

    void resize_table(std::size_t megabytes) {
        std::size_t bytes = std::max<std::size_t>(1, megabytes) * 1024 * 1024;
        std::size_t entries = std::max<std::size_t>(
            256,
            bytes / sizeof(TTCluster)
        );
        std::size_t power = 1;
        while (power * 2 <= entries) {
            power *= 2;
        }
        table_.assign(power, TTCluster{});
    }

    void clear() {
        std::fill(table_.begin(), table_.end(), TTCluster{});
        history_ = {};
        capture_history_ = {};
        killers_ = {};
        countermoves_ = {};
        continuation_history_ = {};
    }

    struct Result {
        Move move{};
        int score = 0;
        int depth = 0;
        uint64_t nodes = 0;
        int hashfull = 0;
        long long elapsed_ms = 0;
        std::vector<Move> pv;
    };

    struct RootMoveResult {
        bool complete = false;
        int score = -INF;
        uint64_t nodes = 0;
    };

    void begin_parallel_search() {
        ++generation_;
    }

    RootMoveResult search_root_move(
        const Board& position,
        const Move& move,
        int depth,
        int alpha,
        int beta,
        const std::vector<uint64_t>& game_history,
        std::chrono::steady_clock::time_point deadline
    ) {
        nodes_ = 0;
        node_limit_ = 0;
        static_evals_.fill(-INF);
        search_history_ = game_history;
        deadline_ = deadline;
        RootMoveResult result;
        if (std::chrono::steady_clock::now() >= deadline_) {
            return result;
        }
        Board board = position;
        board.make_move(move);
        try {
            result.score = -negamax(
                board,
                depth - 1,
                -beta,
                -alpha,
                1,
                true,
                move
            );
            result.complete = true;
        } catch (const Timeout&) {
            result.complete = false;
        }
        result.nodes = nodes_;
        return result;
    }

    int table_hashfull() const {
        return hashfull();
    }

    int see(const Board& position, const Move& move) const {
        return static_exchange_evaluation(position, move);
    }

    std::vector<Move> line_after_move(
        const Board& position,
        const Move& move,
        int depth
    ) {
        std::vector<Move> line{move};
        if (depth <= 1) {
            return line;
        }
        Board board = position;
        board.make_move(move);
        auto tail = principal_variation(board, depth - 1);
        line.insert(line.end(), tail.begin(), tail.end());
        return line;
    }

    Result search(
        const Board& position,
        int max_depth,
        int move_time_ms,
        const std::vector<uint64_t>& game_history = {},
        uint64_t node_limit = 0
    ) {
        nodes_ = 0;
        node_limit_ = node_limit;
        static_evals_.fill(-INF);
        ++generation_;
        search_history_ = game_history;
        deadline_ = std::chrono::steady_clock::now()
            + std::chrono::milliseconds(std::max(1, move_time_ms));
        auto started = std::chrono::steady_clock::now();
        Result result;
        Board board = position;
        auto legal = board.legal_moves_in_place();
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
                    auto [score, move] = root(board, depth, alpha, beta);
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
        result.hashfull = hashfull();
        result.elapsed_ms = std::chrono::duration_cast<std::chrono::milliseconds>(
            std::chrono::steady_clock::now() - started
        ).count();
        result.pv = principal_variation(position, result.depth);
        return result;
    }

private:
    std::vector<TTCluster> table_;
    std::array<std::array<Move, 2>, MAX_PLY> killers_{};
    std::array<std::array<int, 64>, 128> history_{};
    std::array<std::array<int, 64>, 128> capture_history_{};
    std::array<std::array<Move, 64>, 128> countermoves_{};
    std::array<std::array<int, 64>, 64> continuation_history_{};
    std::array<int, MAX_PLY> static_evals_{};
    std::vector<uint64_t> search_history_;
    uint64_t nodes_ = 0;
    uint64_t node_limit_ = 0;
    uint16_t generation_ = 0;
    std::chrono::steady_clock::time_point deadline_{};

    int hashfull() const {
        std::size_t sample = std::min<std::size_t>(1000, table_.size());
        std::size_t occupied = 0;
        for (std::size_t index = 0; index < sample; ++index) {
            for (const TTEntry& entry : table_[index].entries) {
                occupied += entry.depth >= 0
                    && entry.generation == generation_;
            }
        }
        return static_cast<int>(
            occupied * 1000 / std::max<std::size_t>(1, sample * TTCluster::SIZE)
        );
    }

    void check_time() {
        if ((nodes_ & 2047ULL) == 0) {
            if ((node_limit_ != 0 && nodes_ >= node_limit_)
                || std::chrono::steady_clock::now() >= deadline_) {
                throw Timeout{};
            }
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

    int least_valuable_attacker(
        const Board& board,
        int target,
        bool white
    ) const {
        uint64_t target_bit = square_bit(target);
        uint64_t pawn_sources = white
            ? ((target_bit & ~FILE_A) << 7)
                | ((target_bit & ~FILE_H) << 9)
            : ((target_bit & ~FILE_H) >> 7)
                | ((target_bit & ~FILE_A) >> 9);
        uint64_t pawn = pawn_sources & board.piece_boards[
            Zobrist::piece_index(white ? 'P' : 'p')
        ];
        if (pawn != 0) {
            return static_cast<int>(std::countr_zero(pawn));
        }
        uint64_t knight = KNIGHT_ATTACKS[target] & board.piece_boards[
            Zobrist::piece_index(white ? 'N' : 'n')
        ];
        if (knight != 0) {
            return static_cast<int>(std::countr_zero(knight));
        }
        uint64_t bishop_attacker = board.bishop_attacks(target)
            & board.piece_boards[Zobrist::piece_index(white ? 'B' : 'b')];
        if (bishop_attacker != 0) {
            return static_cast<int>(std::countr_zero(bishop_attacker));
        }
        uint64_t rook_attacker = board.rook_attacks(target)
            & board.piece_boards[Zobrist::piece_index(white ? 'R' : 'r')];
        if (rook_attacker != 0) {
            return static_cast<int>(std::countr_zero(rook_attacker));
        }
        uint64_t queen = (
            board.bishop_attacks(target) | board.rook_attacks(target)
        ) & board.piece_boards[Zobrist::piece_index(white ? 'Q' : 'q')];
        if (queen != 0) {
            return static_cast<int>(std::countr_zero(queen));
        }
        uint64_t king = KING_ATTACKS[target] & board.piece_boards[
            Zobrist::piece_index(white ? 'K' : 'k')
        ];
        return king == 0 ? -1 : static_cast<int>(std::countr_zero(king));
    }

    int static_exchange_evaluation(const Board& board, const Move& move) const {
        std::array<int, 32> gains{};
        gains[0] = capture_value(board, move);
        Board position = board;
        position.make_move(move);
        int target = move.to;
        int count = 1;

        while (count < static_cast<int>(gains.size())) {
            int source = least_valuable_attacker(
                position,
                target,
                position.white_to_move
            );
            if (source < 0 || position.squares[target] == '.') {
                break;
            }
            char attacker = position.squares[source];
            char captured = position.squares[target];
            int promotion_gain = 0;
            int target_row = target / 8;
            if (std::tolower(attacker) == 'p'
                && (target_row == 0 || target_row == 7)) {
                promotion_gain = PIECE_VALUES[static_cast<int>('q')]
                    - PIECE_VALUES[static_cast<int>('p')];
                attacker = position.white_to_move ? 'Q' : 'q';
            }
            gains[count] = PIECE_VALUES[static_cast<int>(captured)]
                + promotion_gain - gains[count - 1];
            position.remove_piece(source);
            position.remove_piece(target);
            position.place_piece(attacker, target);
            position.white_to_move = !position.white_to_move;
            ++count;
        }
        while (--count > 0) {
            gains[count - 1] = -std::max(-gains[count - 1], gains[count]);
        }
        return gains[0];
    }

    bool quiet(const Board& board, const Move& move) const {
        return board.squares[move.to] == '.'
            && !(move.flags & EN_PASSANT) && move.promotion == '\0';
    }

    bool pawn_attacked(const Board& board, int target, bool by_white) const {
        return (board.pawn_attacks(by_white) & square_bit(target)) != 0;
    }

    void update_history(char piece, int target, int bonus) {
        constexpr int HISTORY_LIMIT = 16'384;
        bonus = std::clamp(bonus, -HISTORY_LIMIT, HISTORY_LIMIT);
        int& value = history_[static_cast<int>(piece)][target];
        value += bonus - value * std::abs(bonus) / HISTORY_LIMIT;
    }

    void update_capture_history(char piece, int target, int bonus) {
        constexpr int HISTORY_LIMIT = 16'384;
        bonus = std::clamp(bonus, -HISTORY_LIMIT, HISTORY_LIMIT);
        int& value = capture_history_[static_cast<int>(piece)][target];
        value += bonus - value * std::abs(bonus) / HISTORY_LIMIT;
    }

    void update_continuation_history(int previous, int target, int bonus) {
        constexpr int HISTORY_LIMIT = 16'384;
        bonus = std::clamp(bonus, -HISTORY_LIMIT, HISTORY_LIMIT);
        int& value = continuation_history_[previous][target];
        value += bonus - value * std::abs(bonus) / HISTORY_LIMIT;
    }

    template <typename Moves>
    void order_moves(
        const Board& board,
        Moves& moves,
        const Move& tt_move,
        int ply,
        const Move& counter_move = Move{},
        const Move& previous_move = Move{}
    ) {
        auto score = [&](const Move& move) {
            if (tt_move.valid() && move == tt_move) {
                return 10'000'000;
            }
            char piece = board.squares[move.from];
            char victim = board.squares[move.to];
            int value = 0;
            if (victim != '.' || (move.flags & EN_PASSANT)) {
                int exchange = static_exchange_evaluation(board, move);
                value += (exchange >= 0 ? 1'000'000 : -100'000)
                    + 16 * capture_value(board, move)
                    - PIECE_VALUES[static_cast<int>(piece)]
                    + 32 * exchange;
                value += capture_history_[static_cast<int>(piece)][move.to];
            }
            if (move.promotion != '\0') {
                value += 1'500'000
                    + PIECE_VALUES[static_cast<int>(move.promotion)];
            }
            if (ply < MAX_PLY) {
                if (move == killers_[ply][0]) value += 700'000;
                if (move == killers_[ply][1]) value += 690'000;
            }
            if (counter_move.valid() && move == counter_move) {
                value += 680'000;
            }
            value += history_[static_cast<int>(piece)][move.to];
            if (previous_move.valid() && quiet(board, move)) {
                value += continuation_history_[previous_move.to][move.to];
            }
            if (quiet(board, move)) {
                bool enemy_white = !is_white(piece);
                int threat_delta = static_cast<int>(
                    pawn_attacked(board, move.from, enemy_white)
                ) - static_cast<int>(
                    pawn_attacked(board, move.to, enemy_white)
                );
                value += threat_delta
                    * PIECE_VALUES[static_cast<int>(piece)] * 8;
            }
            if (move.flags & CASTLING) value += 25'000;
            return value;
        };
        using ScoredMove = std::pair<int, Move>;
        FixedList<ScoredMove, 256> scored;
        for (const Move& move : moves) {
            scored.push_back({score(move), move});
        }
        std::sort(
            scored.begin(),
            scored.end(),
            [](const auto& left, const auto& right) {
                if (left.first != right.first) {
                    return left.first > right.first;
                }
                if (left.second.from != right.second.from) {
                    return left.second.from < right.second.from;
                }
                if (left.second.to != right.second.to) {
                    return left.second.to < right.second.to;
                }
                return left.second.promotion < right.second.promotion;
            }
        );
        for (std::size_t index = 0; index < moves.size(); ++index) {
            moves[index] = scored[index].second;
        }
    }

    TTEntry* probe(uint64_t key) {
        TTCluster& cluster = table_[key & (table_.size() - 1)];
        for (TTEntry& entry : cluster.entries) {
            if (entry.depth >= 0 && entry.key == key) {
                return &entry;
            }
        }
        return nullptr;
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
        int ply,
        int static_eval = INF
    ) {
        TTCluster& cluster = table_[key & (table_.size() - 1)];
        TTEntry* target = &cluster.entries[0];
        for (TTEntry& candidate : cluster.entries) {
            if (candidate.depth >= 0 && candidate.key == key) {
                target = &candidate;
                break;
            }
            int candidate_priority = candidate.depth
                - (candidate.generation == generation_ ? 0 : 8);
            int target_priority = target->depth
                - (target->generation == generation_ ? 0 : 8);
            if (candidate_priority < target_priority) {
                target = &candidate;
            }
        }
        bool same_position = target->depth >= 0 && target->key == key;
        if (!same_position || depth >= target->depth || bound == Bound::Exact) {
            *target = {
                key,
                depth,
                score_to_table(score, ply),
                static_eval,
                bound,
                move,
                generation_
            };
        }
    }

    std::pair<int, Move> root(
        Board& board,
        int depth,
        int alpha,
        int beta
    ) {
        check_time();
        uint64_t key = board.key;
        TTEntry* entry = probe(key);
        Move tt_move = entry == nullptr ? Move{} : entry->move;
        auto moves = board.legal_moves_in_place();
        order_moves(board, moves, tt_move, 0);
        Move best = moves.front();
        int best_score = -INF;
        int original_alpha = alpha;

        for (std::size_t index = 0; index < moves.size(); ++index) {
            ScopedMove applied(board, moves[index]);
            int score;
            if (index == 0) {
                score = -negamax(
                    board, depth - 1, -beta, -alpha, 1, true, moves[index]
                );
            } else {
                score = -negamax(
                    board,
                    depth - 1,
                    -alpha - 1,
                    -alpha,
                    1,
                    true,
                    moves[index]
                );
                if (score > alpha && score < beta) {
                    score = -negamax(
                        board, depth - 1, -beta, -alpha, 1, true, moves[index]
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
        Board& board,
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

        uint64_t key = board.key;
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
        int static_eval = in_check
            ? -INF
            : (entry != nullptr && entry->static_eval != INF
                ? entry->static_eval
                : evaluate(board));
        static_evals_[ply] = static_eval;
        bool improving = !in_check
            && ply >= 2
            && static_evals_[ply - 2] != -INF
            && static_eval > static_evals_[ply - 2];
        if (
            !in_check
            && depth <= 3
            && beta - alpha == 1
            && std::abs(beta) < MATE - MAX_PLY
            && static_eval - (improving ? 65 : 90) * depth >= beta
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
            null_board.key ^= ZOBRIST.turn;
            if (null_board.en_passant >= 0) {
                null_board.key ^= ZOBRIST.ep_file[null_board.en_passant % 8];
            }
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
                if (prior_visits > 0) {
                    // Avoid null cutoffs near an actual repetition cycle.
                } else if (depth < 7) {
                    return score;
                } else {
                    int verification = negamax(
                        board,
                        depth - 1 - reduction,
                        beta - 1,
                        beta,
                        ply,
                        false,
                        previous_move
                    );
                    if (verification >= beta) {
                        return verification;
                    }
                }
            }
        }

        if (
            depth >= 6
            && beta - alpha == 1
            && (entry == nullptr || !entry->move.valid())
        ) {
            --depth;
        }

        auto moves = board.legal_moves_in_place();
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
        order_moves(board, moves, tt_move, ply, counter_move, previous_move);
        int original_alpha = alpha;
        int best_score = -INF;
        Move best{};
        int static_score = depth <= 2 && !in_check ? static_eval : -INF;
        MoveList quiets_tried;
        MoveList captures_tried;

        for (std::size_t index = 0; index < moves.size(); ++index) {
            const Move& move = moves[index];
            bool is_quiet = quiet(board, move);
            char moving_piece = board.squares[move.from];
            int score = -INF;
            bool pruned = false;
            {
                ScopedMove applied(board, move);
                bool gives_check = board.in_check();
                if (
                    depth <= 2
                    && index >= static_cast<std::size_t>(
                        8 + depth * 4 + (improving ? 4 : 0)
                    )
                    && is_quiet
                    && !in_check
                    && !gives_check
                    && static_eval + 110 * depth <= alpha
                ) {
                    pruned = true;
                }
                if (depth == 1 && index > 0 && is_quiet && !gives_check
                    && static_score + 140 <= alpha) {
                    pruned = true;
                }
                if (!pruned) {
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
                            static_cast<int>(moving_piece)
                        ][move.to];
                        if (
                            history_score > 4'000
                            || move == killers_[ply][0]
                            || move == counter_move
                        ) {
                            --reduction;
                        }
                        if (improving) {
                            --reduction;
                        }
                        reduction = std::clamp(
                            reduction,
                            1,
                            std::max(1, next_depth - 1)
                        );
                    }

                    if (index == 0) {
                        score = -negamax(
                            board,
                            next_depth,
                            -beta,
                            -alpha,
                            ply + 1,
                            true,
                            move
                        );
                    } else {
                        score = -negamax(
                            board,
                            std::max(0, next_depth - reduction),
                            -alpha - 1,
                            -alpha,
                            ply + 1,
                            true,
                            move
                        );
                        if (reduction != 0 && score > alpha) {
                            score = -negamax(
                                board,
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
                                board,
                                next_depth,
                                -beta,
                                -alpha,
                                ply + 1,
                                true,
                                move
                            );
                        }
                    }
                }
            }
            if (pruned) {
                continue;
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
                    update_history(moving_piece, move.to, bonus);
                    if (previous_move.valid()) {
                        update_continuation_history(
                            previous_move.to,
                            move.to,
                            bonus
                        );
                    }
                    for (const Move& previous : quiets_tried) {
                        update_history(
                            board.squares[previous.from],
                            previous.to,
                            -bonus / 2
                        );
                        if (previous_move.valid()) {
                            update_continuation_history(
                                previous_move.to,
                                previous.to,
                                -bonus / 2
                            );
                        }
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
                } else {
                    int bonus = std::min(16'384, depth * depth * 24);
                    update_capture_history(
                        moving_piece,
                        move.to,
                        bonus
                    );
                    for (const Move& previous : captures_tried) {
                        update_capture_history(
                            board.squares[previous.from],
                            previous.to,
                            -bonus / 2
                        );
                    }
                }
                break;
            }
            if (is_quiet) {
                quiets_tried.push_back(move);
            } else {
                captures_tried.push_back(move);
            }
        }
        Bound bound = best_score <= original_alpha
            ? Bound::Upper
            : (best_score >= beta ? Bound::Lower : Bound::Exact);
        store(key, depth, best_score, bound, best, ply, static_eval);
        return best_score;
    }

    int quiescence(
        Board& board,
        int alpha,
        int beta,
        int ply,
        int qply
    ) {
        ++nodes_;
        check_time();
        bool in_check = board.in_check();
        uint64_t key = board.key;
        TTEntry* entry = probe(key);
        if (entry != nullptr && entry->depth >= 0) {
            int table_score = score_from_table(entry->score, ply);
            if (entry->bound == Bound::Exact) return table_score;
            if (entry->bound == Bound::Lower && table_score >= beta) {
                return table_score;
            }
            if (entry->bound == Bound::Upper && table_score <= alpha) {
                return table_score;
            }
        }
        int original_alpha = alpha;
        int stand_pat = in_check
            ? -INF
            : (entry != nullptr && entry->static_eval != INF
                ? entry->static_eval
                : evaluate(board));
        if (!in_check) {
            if (stand_pat >= beta) {
                store(
                    key,
                    0,
                    stand_pat,
                    Bound::Lower,
                    Move{},
                    ply,
                    stand_pat
                );
                return stand_pat;
            }
            alpha = std::max(alpha, stand_pat);
            if (qply >= 10) {
                return stand_pat;
            }
        }
        auto moves = board.legal_moves_in_place(!in_check);
        if (moves.empty()) {
            return in_check ? -MATE + ply : alpha;
        }
        Move tt_move = entry == nullptr ? Move{} : entry->move;
        order_moves(board, moves, tt_move, ply);
        Move best{};
        for (const Move& move : moves) {
            if (!in_check && move.promotion == '\0'
                && stand_pat + capture_value(board, move) + 140 < alpha) {
                continue;
            }
            ScopedMove applied(board, move);
            int score = -quiescence(board, -beta, -alpha, ply + 1, qply + 1);
            if (score >= beta) {
                store(
                    key,
                    0,
                    score,
                    Bound::Lower,
                    move,
                    ply,
                    in_check ? INF : stand_pat
                );
                return score;
            }
            if (score > alpha) {
                alpha = score;
                best = move;
            }
        }
        Bound bound = alpha > original_alpha ? Bound::Exact : Bound::Upper;
        store(
            key,
            0,
            alpha,
            bound,
            best,
            ply,
            in_check ? INF : stand_pat
        );
        return alpha;
    }

    bool has_non_pawn_material(const Board& board) const {
        uint64_t side = board.color_boards[
            Board::color_index(board.white_to_move)
        ];
        uint64_t pawns = board.piece_boards[
            Zobrist::piece_index(board.white_to_move ? 'P' : 'p')
        ];
        uint64_t king = board.piece_boards[
            Zobrist::piece_index(board.white_to_move ? 'K' : 'k')
        ];
        return (side & ~(pawns | king)) != 0;
    }

    std::vector<Move> principal_variation(Board board, int depth) {
        std::vector<Move> pv;
        for (int index = 0; index < depth; ++index) {
            TTEntry* entry = probe(board.key);
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

class EnginePool {
public:
    explicit EnginePool(std::size_t hash_megabytes = 64)
        : hash_megabytes_(hash_megabytes) {
        rebuild();
    }

    void resize_table(std::size_t megabytes) {
        hash_megabytes_ = std::max<std::size_t>(1, megabytes);
        rebuild();
    }

    void set_threads(int threads) {
        int selected = std::clamp(threads, 1, 64);
        if (selected != thread_count_) {
            thread_count_ = selected;
            rebuild();
        }
    }

    int threads() const {
        return thread_count_;
    }

    void clear() {
        for (const auto& worker : workers_) {
            worker->clear();
        }
    }

    Engine::Result search(
        const Board& position,
        int max_depth,
        int move_time_ms,
        const std::vector<uint64_t>& game_history = {},
        uint64_t node_limit = 0
    ) {
        if (thread_count_ == 1 || node_limit != 0) {
            return workers_.front()->search(
                position,
                max_depth,
                move_time_ms,
                game_history,
                node_limit
            );
        }
        return parallel_search(
            position,
            max_depth,
            move_time_ms,
            game_history
        );
    }

private:
    std::size_t hash_megabytes_ = 64;
    int thread_count_ = 1;
    std::vector<std::unique_ptr<Engine>> workers_;

    void rebuild() {
        workers_.clear();
        std::size_t per_worker = std::max<std::size_t>(
            1,
            hash_megabytes_ / static_cast<std::size_t>(thread_count_)
        );
        workers_.reserve(static_cast<std::size_t>(thread_count_));
        for (int index = 0; index < thread_count_; ++index) {
            workers_.push_back(std::make_unique<Engine>(per_worker));
        }
    }

    int average_hashfull() const {
        int total = 0;
        for (const auto& worker : workers_) {
            total += worker->table_hashfull();
        }
        return total / std::max(1, thread_count_);
    }

    Engine::Result parallel_search(
        const Board& position,
        int max_depth,
        int move_time_ms,
        const std::vector<uint64_t>& game_history
    ) {
        auto started = std::chrono::steady_clock::now();
        auto deadline = started
            + std::chrono::milliseconds(std::max(1, move_time_ms));
        Engine::Result result;
        auto moves = position.legal_moves();
        if (moves.empty()) {
            return result;
        }
        result.move = moves.front();
        result.pv = {result.move};
        for (const auto& worker : workers_) {
            worker->begin_parallel_search();
        }
        uint64_t total_nodes = 0;

        for (int depth = 1; depth <= max_depth; ++depth) {
            if (std::chrono::steady_clock::now() >= deadline) {
                break;
            }
            std::vector<int> scores(moves.size(), -INF);
            Engine::RootMoveResult first = workers_.front()->search_root_move(
                position,
                moves.front(),
                depth,
                -INF,
                INF,
                game_history,
                deadline
            );
            total_nodes += first.nodes;
            if (!first.complete) {
                break;
            }
            scores.front() = first.score;
            std::atomic<std::size_t> next_index{1};
            std::atomic<int> shared_alpha{first.score};
            std::atomic<uint64_t> parallel_nodes{0};
            std::atomic<bool> complete{true};
            int best_score = first.score;
            std::size_t best_index = 0;
            int best_worker = 0;
            std::mutex best_mutex;
            int active_workers = std::min<int>(
                thread_count_,
                static_cast<int>(moves.size() - 1)
            );
            std::vector<std::thread> threads;
            threads.reserve(static_cast<std::size_t>(active_workers));

            for (int worker_index = 0;
                worker_index < active_workers;
                ++worker_index) {
                threads.emplace_back([&, worker_index] {
                    Engine& worker = *workers_[worker_index];
                    while (complete.load(std::memory_order_relaxed)) {
                        std::size_t index = next_index.fetch_add(
                            1,
                            std::memory_order_relaxed
                        );
                        if (index >= moves.size()) {
                            break;
                        }
                        int alpha = shared_alpha.load(std::memory_order_relaxed);
                        Engine::RootMoveResult probe = worker.search_root_move(
                            position,
                            moves[index],
                            depth,
                            alpha,
                            alpha + 1,
                            game_history,
                            deadline
                        );
                        parallel_nodes.fetch_add(
                            probe.nodes,
                            std::memory_order_relaxed
                        );
                        if (!probe.complete) {
                            complete.store(false, std::memory_order_relaxed);
                            break;
                        }
                        scores[index] = probe.score;
                        if (probe.score <= alpha) {
                            continue;
                        }
                        Engine::RootMoveResult exact = worker.search_root_move(
                            position,
                            moves[index],
                            depth,
                            alpha,
                            INF,
                            game_history,
                            deadline
                        );
                        parallel_nodes.fetch_add(
                            exact.nodes,
                            std::memory_order_relaxed
                        );
                        if (!exact.complete) {
                            complete.store(false, std::memory_order_relaxed);
                            break;
                        }
                        scores[index] = exact.score;
                        {
                            std::lock_guard<std::mutex> lock(best_mutex);
                            if (exact.score > best_score) {
                                best_score = exact.score;
                                best_index = index;
                                best_worker = worker_index;
                            }
                        }
                        int current = shared_alpha.load(
                            std::memory_order_relaxed
                        );
                        while (exact.score > current
                            && !shared_alpha.compare_exchange_weak(
                                current,
                                exact.score,
                                std::memory_order_relaxed
                            )) {}
                    }
                });
            }
            for (std::thread& thread : threads) {
                thread.join();
            }
            total_nodes += parallel_nodes.load(std::memory_order_relaxed);
            if (!complete.load(std::memory_order_relaxed)) {
                break;
            }

            result.move = moves[best_index];
            result.score = best_score;
            result.depth = depth;
            result.pv = workers_[best_worker]->line_after_move(
                position,
                result.move,
                depth
            );
            std::vector<std::size_t> order(moves.size());
            for (std::size_t index = 0; index < order.size(); ++index) {
                order[index] = index;
            }
            std::stable_sort(
                order.begin(),
                order.end(),
                [&](std::size_t left, std::size_t right) {
                    return scores[left] > scores[right];
                }
            );
            std::vector<Move> ordered_moves;
            ordered_moves.reserve(moves.size());
            for (std::size_t index : order) {
                ordered_moves.push_back(moves[index]);
            }
            moves = std::move(ordered_moves);
            if (std::abs(result.score) > MATE - MAX_PLY) {
                break;
            }
        }
        result.nodes = total_nodes;
        result.hashfull = average_hashfull();
        result.elapsed_ms = std::chrono::duration_cast<std::chrono::milliseconds>(
            std::chrono::steady_clock::now() - started
        ).count();
        return result;
    }
};

uint64_t perft_in_place(Board& board, int depth) {
    if (depth == 0) {
        return 1;
    }
    uint64_t nodes = 0;
    for (const Move& move : board.legal_moves_in_place()) {
        Board::UndoState undo = board.make_move(move);
        nodes += perft_in_place(board, depth - 1);
        board.unmake_move(move, undo);
    }
    return nodes;
}

uint64_t perft(Board board, int depth) {
    return perft_in_place(board, depth);
}

bool verify_keys(Board& board, int depth) {
    if (board.key != ZOBRIST.hash(board)) {
        return false;
    }
    if (depth == 0) {
        return true;
    }
    uint64_t original_key = board.key;
    for (const Move& move : board.legal_moves_in_place()) {
        Board::UndoState undo = board.make_move(move);
        bool valid = verify_keys(board, depth - 1);
        board.unmake_move(move, undo);
        if (!valid || board.key != original_key) {
            return false;
        }
    }
    return true;
}

bool verify_bitboards(Board& board, int depth) {
    if (!board.bitboards_valid()) {
        return false;
    }
    if (depth == 0) {
        return true;
    }
    auto original_pieces = board.piece_boards;
    auto original_colors = board.color_boards;
    uint64_t original_occupied = board.occupied;
    for (const Move& move : board.legal_moves_in_place()) {
        Board::UndoState undo = board.make_move(move);
        bool valid = verify_bitboards(board, depth - 1);
        board.unmake_move(move, undo);
        if (!valid || board.piece_boards != original_pieces
            || board.color_boards != original_colors
            || board.occupied != original_occupied) {
            return false;
        }
    }
    return true;
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
    std::vector<uint64_t>& history
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
    history.push_back(board.key);
    for (std::size_t index = moves_index; index < tokens.size(); ++index) {
        Move move = board.find_move(tokens[index]);
        board.make_move(move);
        history.push_back(board.key);
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
    EnginePool engine;
    std::vector<uint64_t> game_history{board.key};
    int overhead = 10;
    std::string line;
    while (std::getline(std::cin, line)) {
        try {
            if (line == "uci") {
                std::cout << "id name Mwahaha Native Engine 2.3\n";
                std::cout << "id author Mohammed Nabid\n";
                std::cout << "option name Hash type spin default 64 min 1 max 2048\n";
                std::cout << "option name Threads type spin default 1 min 1 max 64\n";
                std::cout << "option name Move Overhead type spin default 10 min 0 max 5000\n";
                std::cout << "uciok\n" << std::flush;
            } else if (line == "isready") {
                std::cout << "readyok\n" << std::flush;
            } else if (line == "ucinewgame") {
                board = Board::starting();
                game_history = {board.key};
                engine.clear();
            } else if (line.rfind("setoption name Hash value ", 0) == 0) {
                engine.resize_table(static_cast<std::size_t>(
                    std::max(1, std::stoi(line.substr(26)))
                ));
            } else if (
                line.rfind("setoption name Threads value ", 0) == 0
            ) {
                engine.set_threads(std::stoi(line.substr(29)));
            } else if (
                line.rfind("setoption name Move Overhead value ", 0) == 0
            ) {
                overhead = std::max(0, std::stoi(line.substr(39)));
            } else if (line.rfind("position ", 0) == 0) {
                parse_position(board, line, game_history);
            } else if (line.rfind("go", 0) == 0) {
                auto tokens = split(line);
                int requested_depth = option_value(tokens, "depth");
                int requested_nodes = option_value(tokens, "nodes");
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
                if (requested_nodes > 0) {
                    move_time = 3'600'000;
                }
                Engine::Result result = engine.search(
                    board,
                    depth,
                    move_time,
                    game_history,
                    static_cast<uint64_t>(std::max(0, requested_nodes))
                );
                uint64_t nps = result.nodes * 1000
                    / static_cast<uint64_t>(std::max<long long>(1, result.elapsed_ms));
                std::cout << "info depth " << result.depth
                    << " score cp " << result.score
                    << " nodes " << result.nodes
                    << " nps " << nps
                    << " hashfull " << result.hashfull
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
    if (argc >= 4 && std::string(argv[1]) == "--see-fen") {
        std::ostringstream fen;
        for (int index = 3; index < argc; ++index) {
            if (index != 3) fen << ' ';
            fen << argv[index];
        }
        Board board = Board::from_fen(fen.str());
        Move move = board.find_move(argv[2]);
        Engine engine(1);
        std::cout << engine.see(board, move) << '\n';
        return 0;
    }
    if (argc == 3 && std::string(argv[1]) == "--verify-bitboards") {
        Board board = Board::starting();
        bool valid = verify_bitboards(board, std::stoi(argv[2]));
        std::cout << (valid ? "bitboards ok\n" : "bitboard mismatch\n");
        return valid ? 0 : 1;
    }
    if (argc >= 4 && std::string(argv[1]) == "--verify-bitboards-fen") {
        int depth = std::stoi(argv[2]);
        std::ostringstream fen;
        for (int index = 3; index < argc; ++index) {
            if (index != 3) fen << ' ';
            fen << argv[index];
        }
        Board board = Board::from_fen(fen.str());
        bool valid = verify_bitboards(board, depth);
        std::cout << (valid ? "bitboards ok\n" : "bitboard mismatch\n");
        return valid ? 0 : 1;
    }
    if (argc == 3 && std::string(argv[1]) == "--verify-keys") {
        Board board = Board::starting();
        bool valid = verify_keys(board, std::stoi(argv[2]));
        std::cout << (valid ? "keys ok\n" : "key mismatch\n");
        return valid ? 0 : 1;
    }
    if (argc >= 4 && std::string(argv[1]) == "--verify-keys-fen") {
        int depth = std::stoi(argv[2]);
        std::ostringstream fen;
        for (int index = 3; index < argc; ++index) {
            if (index != 3) fen << ' ';
            fen << argv[index];
        }
        Board board = Board::from_fen(fen.str());
        bool valid = verify_keys(board, depth);
        std::cout << (valid ? "keys ok\n" : "key mismatch\n");
        return valid ? 0 : 1;
    }
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
