# OptiTrack Trigger (Interactive Rigid Body Sampler)

Minimal script to manually sample a single OptiTrack rigid body pose from Motive (NatNet) and write rows to CSV.

## Use
Press Enter to record, `p` to peek (no record), `q` or Ctrl+C to save & exit.

## Run

You will want to modify ip if you're motive streaming on a different workstation.

```powershell
# Default (millimeters; scale=1000)
python .\capture.py --local-ip 127.0.0.1 --server-ip 127.0.0.1 --rbid 1

# Specify outfile
python .\capture.py --local-ip 127.0.0.1 --server-ip 127.0.0.1 --rbid 1 --outfile .\samples.csv

# Meters instead of mm
python .\capture.py --local-ip 127.0.0.1 --server-ip 127.0.0.1 --rbid 1 --position-scale 1.0 # This gives meters
```

If `--outfile` omitted → `optitrack_samples_YYYYMMDD_HHMMSS.csv`.

## Args
`--local-ip` your machine IP
`--server-ip` Motive host IP
`--rbid` rigid body Streaming ID (from Motive properties)
`--outfile` CSV path (optional)
`--position-scale` 1000.0=mm (default), 1.0=m

## CSV columns
`event_time` (capture press epoch)
`frame_time` (latest NatNet frame epoch)
`age_ms` (freshness: (event_time - frame_time)*1000)
`x,y,z` (scaled position)
`qx,qy,qz,qw` (quaternion)
`rigid_body_id`

Example:
```csv
event_time,frame_time,age_ms,x,y,z,qx,qy,qz,qw,rigid_body_id
1762551001.3992,1762551001.3952,4.03,-0.01314,-0.01038,0.33828,-0.01550,-0.99721,0.00271,-0.07304,1
```

## Requirements
Python 3.8+, Motive (NatNet enabled, check your data stream pane), UDP ports 1510/1511 allowed.

## Tips
- "No data yet" → check IPs, firewall, Streaming ID.
- Age large? Network delay or slow frame arrival.

