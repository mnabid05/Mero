//! Standalone SCReLU pilot for Mero. The pinned backend's progression example
//! documents dual-perspective concatenation and output-weight serialization.
use bullet_lib::{
    game::{inputs::Chess768, outputs::MaterialCount},
    nn::optimiser::AdamW,
    trainer::{save::SavedFormat, schedule::{TrainingSchedule, TrainingSteps, lr, wdl}, settings::LocalSettings},
    value::{ValueTrainerBuilder, loader::DirectSequentialDataLoader},
};
use std::{env, fs, io::Write, path::Path};

fn main() -> Result<(), Box<dyn std::error::Error>> {
    let args: Vec<_> = env::args().collect();
    if args.len()!=5 {
        return Err("arguments: TRAIN.bullet NEW_CHECKPOINT_DIR SUPERBATCHES PARITY_FENS".into());
    }
    let rows=fs::metadata(&args[1])?.len();
    let rounds: usize=args[3].parse()?;
    if rows%32!=0 || rows<512*32 || !(2..=1024).contains(&rounds) {
        return Err("need whole records, >=512 examples, and 2-1024 superbatches".into());
    }
    let fens=fs::read_to_string(&args[4])?;
    fs::create_dir(&args[2])?; // never silently resume or clobber an experiment
    let backend=ValueTrainerBuilder::default()
        .inputs(Chess768).dual_perspective().output_buckets(MaterialCount::<8>)
        .optimiser(AdamW)
        .save_format(&[
            SavedFormat::id("ftw").round().quantise::<i16>(255),
            SavedFormat::id("ftb").round().quantise::<i16>(255),
            SavedFormat::id("readw").round().quantise::<i16>(64).transpose(),
            SavedFormat::id("readb").round().quantise::<i16>(255*64),
        ])
        .loss_fn(|out,y| out.sigmoid().squared_error(y));
    let mut trainer=backend.build(|g,us,them,bucket| {
        let ft=g.new_affine("ft",768,512);
        let read=g.new_affine("read",1024,8);
        read.forward(ft.forward(us).screlu().concat(ft.forward(them).screlu())).select(bucket)
    });
    let schedule=TrainingSchedule {
        net_id: "mero-bullet".into(), eval_scale: 400.0,
        steps: TrainingSteps { batch_size:512,batches_per_superbatch:(rows/32/512) as usize,
            start_superbatch:1,end_superbatch:rounds },
        wdl_scheduler:wdl::ConstantWDL { value:0.35 },
        lr_scheduler:lr::CosineDecayLR { initial_lr:0.001,final_lr:0.00003,final_superbatch:rounds },
        save_rate:5,
    };
    let settings=LocalSettings { threads:2, test_set:None, output_directory:&args[2], batch_queue_size:4 };
    trainer.run(&schedule,&settings,&DirectSequentialDataLoader::new(&[&args[1]]));
    let mut parity=fs::File::create(Path::new(&args[2]).join("final-float-parity.tsv"))?;
    for fen in fens.lines().filter(|s| !s.trim().is_empty()) {
        writeln!(parity,"{}\t{}",fen,trainer.eval(fen)*400.0)?;
    }
    Ok(())
}
