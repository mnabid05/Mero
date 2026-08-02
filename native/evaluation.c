#include <stddef.h>
#include <stdlib.h>

#if defined(_WIN32)
#define MWAHAHA_EXPORT __declspec(dllexport)
#else
#define MWAHAHA_EXPORT __attribute__((visibility("default")))
#endif

enum { WHITE = 0, BLACK = 1, MAX_PHASE = 24 };

static int color_of(char piece) {
    return piece >= 'A' && piece <= 'Z' ? WHITE : BLACK;
}

static char lower_piece(char piece) {
    return piece >= 'A' && piece <= 'Z' ? (char)(piece + ('a' - 'A')) : piece;
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

static int square_bonus(int square, char type, int color, int endgame) {
    int row = row_of(square);
    int column = column_of(square);
    int relative_rank = color == WHITE ? 7 - row : row;
    double center =
        7.0 - (abs(7 - 2 * row) / 2.0 + abs(7 - 2 * column) / 2.0);
    int edge = (column == 0 || column == 7) + (row == 0 || row == 7);

    switch (type) {
        case 'p':
            return relative_rank * (endgame ? 13 : 7) + (int)(center * 2);
        case 'n':
            return (int)(center * (endgame ? 9 : 11)) - edge * 18;
        case 'b':
            return (int)(center * 6) + relative_rank * 2;
        case 'r':
            return relative_rank * (endgame ? 4 : 2);
        case 'q':
            return (int)(center * (endgame ? 3 : 1));
        case 'k':
            if (endgame) {
                return (int)(center * 10);
            }
            return (column == 1 || column == 2 || column == 6 ? 24 : 0)
                - (int)(center * 12);
        default:
            return 0;
    }
}

static int is_passed(
    const char board[64],
    int square,
    int color
) {
    int row = row_of(square);
    int column = column_of(square);
    char enemy = color == WHITE ? 'p' : 'P';
    int start = color == WHITE ? 0 : row + 1;
    int stop = color == WHITE ? row : 8;

    for (int enemy_row = start; enemy_row < stop; ++enemy_row) {
        for (int delta = -1; delta <= 1; ++delta) {
            int enemy_column = column + delta;
            if (in_bounds(enemy_row, enemy_column)
                && board[enemy_row * 8 + enemy_column] == enemy) {
                return 0;
            }
        }
    }
    return 1;
}

static void pawn_structure(
    const char board[64],
    int color,
    int *middle,
    int *end
) {
    char pawn = color == WHITE ? 'P' : 'p';
    int file_counts[8] = {0};

    for (int square = 0; square < 64; ++square) {
        if (board[square] == pawn) {
            ++file_counts[column_of(square)];
        }
    }

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

    for (int square = 0; square < 64; ++square) {
        if (board[square] != pawn || !is_passed(board, square, color)) {
            continue;
        }
        int rank = color == WHITE ? 7 - row_of(square) : row_of(square);
        *middle += 10 + rank * rank * 3;
        *end += 20 + rank * rank * 7;
    }
}

static int rook_file_bonus(const char board[64], int color) {
    char rook = color == WHITE ? 'R' : 'r';
    char friendly_pawn = color == WHITE ? 'P' : 'p';
    char enemy_pawn = color == WHITE ? 'p' : 'P';
    int score = 0;

    for (int square = 0; square < 64; ++square) {
        if (board[square] != rook) {
            continue;
        }
        int file = column_of(square);
        int friendly = 0;
        int enemy = 0;
        for (int row = 0; row < 8; ++row) {
            friendly |= board[row * 8 + file] == friendly_pawn;
            enemy |= board[row * 8 + file] == enemy_pawn;
        }
        if (!friendly) {
            score += 14;
            if (!enemy) {
                score += 12;
            }
        }
    }
    return score;
}

static int king_shelter(const char board[64], int color) {
    char king = color == WHITE ? 'K' : 'k';
    char pawn = color == WHITE ? 'P' : 'p';
    int direction = color == WHITE ? -1 : 1;

    for (int square = 0; square < 64; ++square) {
        if (board[square] != king) {
            continue;
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
    return 0;
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

static int mobility(const char board[64], int color) {
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

    for (int square = 0; square < 64; ++square) {
        char piece = board[square];
        if (!occupied(piece) || color_of(piece) != color) {
            continue;
        }
        char type = lower_piece(piece);
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
            size_t count = type == 'n' ? 8 : 8;
            for (size_t index = 0; index < count; ++index) {
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
    }
    return score;
}

MWAHAHA_EXPORT int mwahaha_evaluate(const char board[64]) {
    static const int middle_values[6] = {100, 325, 335, 500, 975, 0};
    static const int end_values[6] = {125, 310, 330, 525, 950, 0};
    static const int phase_values[6] = {0, 1, 1, 2, 4, 0};
    static const char types[7] = "pnbrqk";
    int middle = 0;
    int end = 0;
    int phase = 0;
    int bishops[2] = {0, 0};

    for (int square = 0; square < 64; ++square) {
        char piece = board[square];
        if (!occupied(piece)) {
            continue;
        }
        char type = lower_piece(piece);
        int index = 0;
        while (types[index] != type) {
            ++index;
        }
        int color = color_of(piece);
        int sign = color == WHITE ? 1 : -1;
        phase += phase_values[index];
        bishops[color] += type == 'b';
        middle += sign * (
            middle_values[index] + square_bonus(square, type, color, 0)
        );
        end += sign * (
            end_values[index] + square_bonus(square, type, color, 1)
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
        pawn_structure(board, color, &pawn_middle, &pawn_end);
        middle += sign * (
            pawn_middle
            + rook_file_bonus(board, color)
            + king_shelter(board, color)
            + (bishops[color] >= 2 ? 35 : 0)
        );
        end += sign * (
            pawn_end
            + (bishops[color] >= 2 ? 50 : 0)
        );
    }

    int mobility_difference = mobility(board, WHITE) - mobility(board, BLACK);
    middle += mobility_difference * 3;
    end += mobility_difference * 2;
    if (phase > MAX_PHASE) {
        phase = MAX_PHASE;
    }
    return (middle * phase + end * (MAX_PHASE - phase)) / MAX_PHASE;
}

MWAHAHA_EXPORT int mwahaha_native_api_version(void) {
    return 1;
}
