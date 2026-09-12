This run stopped after three scenarios because the runner read Pome's startup
status JSON before its write completed. These completed snapshots are retained
as an interrupted run, not a complete comparison. The bounded readiness loop
was corrected and the complete rerun is in ../pome-observed-v3/.
