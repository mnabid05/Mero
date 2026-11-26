"""Replay a Mero self-play shard and optionally compare every record with upstream Rust."""
import argparse
import csv
import hashlib
import json
import struct
import subprocess
from collections import Counter
from pathlib import Path
from chess_ai.backtest import repetition_key
from chess_ai.board import Board
from chess_ai.model import GameStatus

def need(value, message):
    if not value:
        raise ValueError(message)

def check_record(raw, board, wdl):
    need(len(raw)==32, "truncated Bullet record")
    occ,pcs,score,result,king,other,padding=struct.unpack("<Q16shBBB3s",raw)
    need(abs(score)<=30_000 and padding==bytes(3), "invalid score or padding")
    actual=[]
    for i in range(64):
        if (occ>>i)&1:
            nibble=(pcs[len(actual)//2]>>(4*(len(actual)%2)))&15
            actual.append((i,nibble))
    expected=sorted((sq^(56 if board.turn=="w" else 0),
                     "pnbrqk".index(pc.lower())+8*((board.turn=="w")!=pc.isupper()))
                    for sq,pc in board.pieces())
    need(expected==actual,"decoded pieces or perspective differ")
    kings={pc:sq for sq,pc in expected if pc in (5,13)}
    need(king==kings[5] and other==(kings[13]^56), "incorrect king metadata")
    need(result==(wdl if board.turn=="w" else 2-wdl),"incorrect WDL orientation")
    return score if board.turn=="w" else -score

def audit(directory, oracle=None):
    meta=json.loads((directory/"COMPLETE.json").read_text())
    need(meta["format"]=="bulletformat-chessboard-v1" and meta["opening_plies"]==8,
         "unknown shard format")
    path=directory/"positions.bullet"
    offsets=games=0
    reasons=Counter()
    outcomes=Counter()
    with path.open("rb") as data,(directory/"games.tsv").open() as source:
        for row in csv.DictReader(source,delimiter="\t"):
            need(int(row["game"])==games and int(row["first"])==offsets, "incorrect game/offset")
            games+=1
            wdl=int(row["white_wdl"])
            plies=list(map(int,filter(None,row["kept_plies"].split(","))))
            wanted=set(plies)
            need(plies==sorted(wanted) and len(plies)==int(row["rows"]), "invalid kept plies")
            moves=row["uci_moves"].split()
            need(all(8<=p<len(moves) for p in plies),"out-of-range record ply")
            board=Board.starting()
            visits=Counter({repetition_key(board):1})
            oracle_rows=[]
            raw_game=bytearray()
            for ply,uci in enumerate(moves):
                move=board.find_legal_move(uci)
                if ply in wanted:
                    need(not (board.is_in_check() or move.promotion or move.is_en_passant or
                         board.squares[move.to_sq]), "nonquiet position entered dataset")
                    raw=data.read(32)
                    white_cp=check_record(raw,board,wdl)
                    if oracle:
                        oracle_rows.append(f"{board.to_fen()} | {white_cp} | {wdl/2:.1f}")
                        raw_game.extend(raw)
                board.push(move)
                visits[repetition_key(board)]+=1
            if oracle_rows:
                ref=subprocess.run([oracle],input=("\n".join(oracle_rows)+"\n").encode(),
                                   capture_output=True,check=True,timeout=60)
                need(ref.stdout==raw_game,"upstream bulletformat did not produce identical bytes")
            status=board.status()
            if status==GameStatus.CHECKMATE: reason,expected="checkmate",0 if board.turn=="w" else 2
            elif status==GameStatus.STALEMATE: reason,expected="stalemate",1
            elif board._has_insufficient_material(): reason,expected="material",1
            elif board.halfmove_clock>=100: reason,expected="rule50",1
            elif visits[repetition_key(board)]>=3: reason,expected="threefold",1
            else:
                need(len(moves)==512 and not plies,"unterminated game supplied labels")
                reason,expected="ply_cap",-1
            need((reason,expected)==(row["termination"],wdl),"incorrect game termination")
            reasons[reason]+=1
            outcomes[wdl]+=1
            offsets+=len(plies)
        need(not data.read(1),"unclaimed records")
    need(offsets==meta["positions"] and games==meta["games"]
         and games-outcomes[-1]==meta["completed"], "manifest totals differ")
    with path.open("rb") as data:
        digest=hashlib.file_digest(data,"sha256").hexdigest()
    return dict(**meta,positions_sha256=digest,upstream_byte_parity=bool(oracle),
                white_wins=outcomes[2],draws=outcomes[1],black_wins=outcomes[0],
                terminal_reasons=dict(reasons))

if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("directory",type=Path)
    p.add_argument("--oracle",type=Path)
    p.add_argument("--report",type=Path)
    a=p.parse_args()
    result=json.dumps(audit(a.directory,a.oracle),indent=2)+"\n"
    if a.report: a.report.write_text(result)
    print(result,end="")
