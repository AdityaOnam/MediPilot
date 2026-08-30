@echo off
set PYTHONIOENCODING=utf-8

echo Training all sequence models sequentially...
python -u -m model.train_seq --models all > train_seq_all.log 2>&1

echo Running Leaderboard...
python -m model.leaderboard --artifacts model\artifacts\medipilot-gbdt-v0.2.0 model\artifacts\medipilot-hist-100k-s1337 model\artifacts\medipilot-last-obs-100k-s1337 model\artifacts\medipilot-gru-100k-s1337 model\artifacts\medipilot-tcn-100k-s1337 model\artifacts\medipilot-transformer-100k-s1337 >> train_seq_all.log 2>&1
echo Done.
