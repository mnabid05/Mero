#include <stddef.h>
#include <stdint.h>

#if defined(_WIN32)
#define MWAHAHA_EXPORT __declspec(dllexport)
#else
#define MWAHAHA_EXPORT __attribute__((visibility("default")))
#endif

enum { WHITE = 0, BLACK = 1, MAX_PHASE = 24 };

static const uint64_t FILE_A = UINT64_C(0x0101010101010101);
static const uint8_t CENTER[64] = {
    0, 1, 2, 3, 3, 2, 1, 0,
    1, 2, 3, 4, 4, 3, 2, 1,
    2, 3, 4, 5, 5, 4, 3, 2,
    3, 4, 5, 6, 6, 5, 4, 3,
    3, 4, 5, 6, 6, 5, 4, 3,
    2, 3, 4, 5, 5, 4, 3, 2,
    1, 2, 3, 4, 4, 3, 2, 1,
    0, 1, 2, 3, 3, 2, 1, 0
};

static int color_of(char piece) {
    return piece >= 'A' && piece <= 'Z' ? WHITE : BLACK;
}

static char lower_piece(char piece) {
    return piece >= 'A' && piece <= 'Z' ? (char)(piece + ('a' - 'A')) : piece;
}

static int piece_index(char type) {
    switch (type) {
        case 'p': return 0;
        case 'n': return 1;
        case 'b': return 2;
        case 'r': return 3;
        case 'q': return 4;
        case 'k': return 5;
        default: return -1;
    }
}

static int occupied(char piece) {
    return piece != '.';
}

static int row_of(int square) {
    return square / 8;
}

static int column_of(int square) {
    return square % 8;
}

static int in_bounds(int row, int column) {
    return row >= 0 && row < 8 && column >= 0 && column < 8;
}

static void square_bonuses(
    int square,
    char type,
    int color,
    int *middle,
    int *end
) {
    int row = row_of(square);
    int column = column_of(square);
    int relative_rank = color == WHITE ? 7 - row : row;
    int center = CENTER[square];
    int edge = (column == 0 || column == 7) + (row == 0 || row == 7);

    switch (type) {
        case 'p':
            *middle = relative_rank * 7 + center * 2;
            *end = relative_rank * 13 + center * 2;
            return;
        case 'n':
            *middle = center * 11 - edge * 18;
            *end = center * 9 - edge * 18;
            return;
        case 'b':
            *middle = *end = center * 6 + relative_rank * 2;
            return;
        case 'r':
            *middle = relative_rank * 2;
            *end = relative_rank * 4;
            return;
        case 'q':
            *middle = center;
            *end = center * 3;
            return;
        case 'k':
            *middle = (column == 1 || column == 2 || column == 6 ? 24 : 0)
                - center * 12;
            *end = center * 10;
            return;
        default:
            *middle = *end = 0;
            return;
    }
}

static int is_passed(uint64_t enemy_pawns, int square, int color) {
    int row = row_of(square);
    int column = column_of(square);
    uint64_t files = FILE_A << column;
    if (column > 0) {
        files |= FILE_A << (column - 1);
    }
    if (column < 7) {
        files |= FILE_A << (column + 1);
    }
    uint64_t ranks;
    if (color == WHITE) {
        ranks = row == 0 ? 0 : (UINT64_C(1) << (row * 8)) - 1;
    } else {
        ranks = row == 7
            ? 0
            : ~((UINT64_C(1) << ((row + 1) * 8)) - 1);
    }
    return (enemy_pawns & files & ranks) == 0;
}

static void pawn_structure(
    int color,
    const int file_counts[8],
    uint64_t friendly_pawns,
    uint64_t enemy_pawns,
    int *middle,
    int *end
) {

    for (int file = 0; file < 8; ++file) {
        if (file_counts[file] > 1) {
            *middle -= (file_counts[file] - 1) * 18;
            *end -= (file_counts[file] - 1) * 24;
        }
        if (
            file_counts[file] > 0
            && (file == 0 || file_counts[file - 1] == 0)
            && (file == 7 || file_counts[file + 1] == 0)
        ) {
            *middle -= file_counts[file] * 14;
            *end -= file_counts[file] * 10;
        }
    }

    while (friendly_pawns != 0) {
        int square = __builtin_ctzll(friendly_pawns);
        friendly_pawns &= friendly_pawns - 1;
        if (!is_passed(enemy_pawns, square, color)) {
            continue;
        }
        int rank = color == WHITE ? 7 - row_of(square) : row_of(square);
        *middle += 10 + rank * rank * 3;
        *end += 20 + rank * rank * 7;
        int row = row_of(square);
        int file = column_of(square);
        uint64_t adjacent_files = 0;
        if (file > 0) adjacent_files |= FILE_A << (file - 1);
        if (file < 7) adjacent_files |= FILE_A << (file + 1);
        uint64_t nearby_ranks = UINT64_C(0xff) << (row * 8);
        if (row > 0) nearby_ranks |= UINT64_C(0xff) << ((row - 1) * 8);
        if (row < 7) nearby_ranks |= UINT64_C(0xff) << ((row + 1) * 8);
        if (friendly_pawns & adjacent_files & nearby_ranks) {
            *middle += 10;
            *end += 18;
        }
    }
}

static int rook_file_bonus(
    int color,
    const int pawn_files[2][8],
    const int rook_files[2][8]
) {
    int score = 0;

    for (int file = 0; file < 8; ++file) {
        if (pawn_files[color][file] == 0) {
            int bonus = 14;
            if (pawn_files[color == WHITE ? BLACK : WHITE][file] == 0) {
                bonus += 12;
            }
            score += rook_files[color][file] * bonus;
        }
    }
    return score;
}

static int king_shelter(const char board[64], int color, int square) {
    char pawn = color == WHITE ? 'P' : 'p';
    int direction = color == WHITE ? -1 : 1;
    if (square < 0) {
        return 0;
    }
    int row = row_of(square) + direction;
    int column = column_of(square);
    int score = 0;
    for (int delta = -1; delta <= 1; ++delta) {
        int target_column = column + delta;
        if (
            in_bounds(row, target_column)
            && board[row * 8 + target_column] == pawn
        ) {
            score += 14;
        }
    }
    return score;
}

static int king_pawn_pressure(uint64_t enemy_pawns, int square) {
    if (square < 0) {
        return 0;
    }
    int king_row = row_of(square);
    int king_file = column_of(square);
    int pressure = 0;
    while (enemy_pawns != 0) {
        int target = __builtin_ctzll(enemy_pawns);
        enemy_pawns &= enemy_pawns - 1;
        int file_distance = column_of(target) - king_file;
        if (file_distance < -1 || file_distance > 1) {
            continue;
        }
        int rank_distance = row_of(target) - king_row;
        if (rank_distance < 0) rank_distance = -rank_distance;
        if (rank_distance <= 3) {
            pressure += 24 - rank_distance * 6;
        }
    }
    return pressure;
}

static int pawn_protects(const char board[64], int square, int color) {
    int row = row_of(square);
    int column = column_of(square);
    int source_row = row + (color == WHITE ? 1 : -1);
    char pawn = color == WHITE ? 'P' : 'p';
    for (int delta = -1; delta <= 1; delta += 2) {
        int source_column = column + delta;
        if (
            in_bounds(source_row, source_column)
            && board[source_row * 8 + source_column] == pawn
        ) {
            return 1;
        }
    }
    return 0;
}

static int enemy_pawn_attacks(const char board[64], int square, int color) {
    return pawn_protects(board, square, color == WHITE ? BLACK : WHITE);
}

static void piece_features(
    const char board[64],
    int square,
    char type,
    int color,
    int *middle,
    int *end
) {
    int row = row_of(square);
    int column = column_of(square);
    int relative_rank = color == WHITE ? 7 - row : row;
    char friendly_pawn = color == WHITE ? 'P' : 'p';

    if (
        type != 'p'
        && type != 'k'
        && enemy_pawn_attacks(board, square, color)
        && !pawn_protects(board, square, color)
    ) {
        int penalty = type == 'q' ? 30 : (type == 'r' ? 20 : 12);
        *middle -= penalty;
        *end -= penalty / 2;
    }

    if (type == 'p') {
        for (int file_delta = -1; file_delta <= 1; file_delta += 2) {
            int neighbor_file = column + file_delta;
            for (int rank_delta = -1; rank_delta <= 1; ++rank_delta) {
                int neighbor_row = row + rank_delta;
                if (
                    in_bounds(neighbor_row, neighbor_file)
                    && board[neighbor_row * 8 + neighbor_file] == friendly_pawn
                ) {
                    *middle += 5;
                    *end += 8;
                    return;
                }
            }
        }
    } else if (
        type == 'n'
        && relative_rank >= 3
        && pawn_protects(board, square, color)
        && !enemy_pawn_attacks(board, square, color)
    ) {
        *middle += 18 + relative_rank * 2;
        *end += 10;
    } else if (type == 'r' && relative_rank == 6) {
        *middle += 18;
        *end += 28;
    }
}

static int ray_mobility(
    const char board[64],
    int square,
    int color,
    const int directions[][2],
    size_t direction_count
) {
    int score = 0;
    int row = row_of(square);
    int column = column_of(square);
    for (size_t index = 0; index < direction_count; ++index) {
        int target_row = row + directions[index][0];
        int target_column = column + directions[index][1];
        while (in_bounds(target_row, target_column)) {
            char target = board[target_row * 8 + target_column];
            if (!occupied(target)) {
                ++score;
            } else {
                score += color_of(target) != color;
                break;
            }
            target_row += directions[index][0];
            target_column += directions[index][1];
        }
    }
    return score;
}

static int piece_mobility(
    const char board[64],
    int square,
    int color,
    char type
) {
    static const int knight_offsets[8][2] = {
        {-2, -1}, {-2, 1}, {-1, -2}, {-1, 2},
        {1, -2}, {1, 2}, {2, -1}, {2, 1}
    };
    static const int bishop_directions[4][2] = {
        {-1, -1}, {-1, 1}, {1, -1}, {1, 1}
    };
    static const int rook_directions[4][2] = {
        {-1, 0}, {1, 0}, {0, -1}, {0, 1}
    };
    static const int queen_directions[8][2] = {
        {-1, -1}, {-1, 1}, {1, -1}, {1, 1},
        {-1, 0}, {1, 0}, {0, -1}, {0, 1}
    };
    int score = 0;
    int row = row_of(square);
    int column = column_of(square);
    if (type == 'p') {
        int direction = color == WHITE ? -1 : 1;
        int start_row = color == WHITE ? 6 : 1;
        int forward_row = row + direction;
        if (in_bounds(forward_row, column)
            && !occupied(board[forward_row * 8 + column])) {
            ++score;
            int second_row = row + 2 * direction;
            if (row == start_row
                && !occupied(board[second_row * 8 + column])) {
                ++score;
            }
        }
        for (int delta = -1; delta <= 1; delta += 2) {
            int target_column = column + delta;
            if (!in_bounds(forward_row, target_column)) {
                continue;
            }
            char target = board[forward_row * 8 + target_column];
            score += occupied(target) && color_of(target) != color;
        }
    } else if (type == 'n' || type == 'k') {
        const int (*offsets)[2] =
            type == 'n' ? knight_offsets : queen_directions;
        for (size_t index = 0; index < 8; ++index) {
            int target_row = row + offsets[index][0];
            int target_column = column + offsets[index][1];
            if (!in_bounds(target_row, target_column)) {
                continue;
            }
            char target = board[target_row * 8 + target_column];
            score += !occupied(target) || color_of(target) != color;
        }
    } else if (type == 'b') {
        score += ray_mobility(board, square, color, bishop_directions, 4);
    } else if (type == 'r') {
        score += ray_mobility(board, square, color, rook_directions, 4);
    } else if (type == 'q') {
        score += ray_mobility(board, square, color, queen_directions, 8);
    }
    return score;
}

static int mobility_difference(const char board[64]) {
    int score = 0;
    for (int square = 0; square < 64; ++square) {
        char piece = board[square];
        if (!occupied(piece)) {
            continue;
        }
        int color = color_of(piece);
        char type = lower_piece(piece);
        int sign = color == WHITE ? 1 : -1;
        score += sign * piece_mobility(board, square, color, type);
    }
    return score;
}

MWAHAHA_EXPORT int mwahaha_evaluate(const char board[64]) {
    static const int middle_values[6] = {100, 325, 335, 500, 975, 0};
    static const int end_values[6] = {125, 310, 330, 525, 950, 0};
    static const int phase_values[6] = {0, 1, 1, 2, 4, 0};
    int middle = 0;
    int end = 0;
    int phase = 0;
    int bishops[2] = {0, 0};
    int pawn_files[2][8] = {{0}};
    uint64_t pawn_bits[2] = {0, 0};
    int rook_files[2][8] = {{0}};
    int king_squares[2] = {-1, -1};

    for (int square = 0; square < 64; ++square) {
        char piece = board[square];
        if (!occupied(piece)) {
            continue;
        }
        char type = lower_piece(piece);
        int index = piece_index(type);
        int color = color_of(piece);
        int sign = color == WHITE ? 1 : -1;
        phase += phase_values[index];
        bishops[color] += type == 'b';
        if (type == 'p') {
            ++pawn_files[color][column_of(square)];
            pawn_bits[color] |= UINT64_C(1) << square;
        } else if (type == 'r') {
            ++rook_files[color][column_of(square)];
        } else if (type == 'k') {
            king_squares[color] = square;
        }
        int square_middle = 0;
        int square_end = 0;
        square_bonuses(
            square,
            type,
            color,
            &square_middle,
            &square_end
        );
        middle += sign * (
            middle_values[index] + square_middle
        );
        end += sign * (
            end_values[index] + square_end
        );
        int feature_middle = 0;
        int feature_end = 0;
        piece_features(
            board,
            square,
            type,
            color,
            &feature_middle,
            &feature_end
        );
        middle += sign * feature_middle;
        end += sign * feature_end;
    }

    for (int color = WHITE; color <= BLACK; ++color) {
        int sign = color == WHITE ? 1 : -1;
        int pawn_middle = 0;
        int pawn_end = 0;
        pawn_structure(
            color,
            pawn_files[color],
            pawn_bits[color],
            pawn_bits[color == WHITE ? BLACK : WHITE],
            &pawn_middle,
            &pawn_end
        );
        middle += sign * (
            pawn_middle
            + rook_file_bonus(color, pawn_files, rook_files)
            + king_shelter(board, color, king_squares[color])
            - king_pawn_pressure(
                pawn_bits[color == WHITE ? BLACK : WHITE],
                king_squares[color]
            )
            + (bishops[color] >= 2 ? 35 : 0)
        );
        end += sign * (
            pawn_end
            + (bishops[color] >= 2 ? 50 : 0)
        );
    }

    int mobility_score = mobility_difference(board);
    middle += mobility_score * 3;
    end += mobility_score * 2;
    if (phase > MAX_PHASE) {
        phase = MAX_PHASE;
    }
    return (middle * phase + end * (MAX_PHASE - phase)) / MAX_PHASE;
}

MWAHAHA_EXPORT int mwahaha_native_api_version(void) {
    return 1;
}
