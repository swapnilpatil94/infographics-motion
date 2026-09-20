# Critique report

Rounds run: 3.  Measured problems before -> after: geometry-bad shots 4 -> 0, pixel flags 15 -> 0, repeated framings 0 -> 0.
VLM mean score (advisory): 6.75 -> 7.9.

## Round 0
geometry-bad shots: 4, pixel flags: 15

- S02 ['head_clipped_x'] -> {'camera': {'zoom_mul': 0.85, 'dx': -166.7, 'dy': 0.0}} 
- S06 ['head_clipped_x', 'head_out_y'] -> {'camera': {'zoom_mul': 0.95, 'dx': -122.1, 'dy': -140.8}} 
- S11 ['head_clipped_x'] -> {'camera': {'zoom_mul': 0.81, 'dx': 196.5, 'dy': 0.0}} 
- S14 ['head_clipped_x'] -> {'camera': {'zoom_mul': 0.99, 'dx': -14.8, 'dy': 0.0}} 
- S01 ['face_too_dark', 'frame_too_dark'] -> {'lighting': {'fill': 0.7, 'exposure_mul': 1.15}} 
- S02 ['face_too_dark'] -> {'lighting': {'fill': 0.7, 'exposure_mul': 1.15}} 
- S03 ['face_too_dark'] -> {'lighting': {'fill': 0.7, 'exposure_mul': 1.15}} 
- S04 ['face_too_dark'] -> {'lighting': {'fill': 0.7, 'exposure_mul': 1.15}} 
- S05 ['face_too_dark'] -> {'lighting': {'fill': 0.7, 'exposure_mul': 1.15}} 
- S06 ['face_too_dark'] -> {'lighting': {'fill': 0.7, 'exposure_mul': 1.15}} 
- S07 ['face_too_dark'] -> {'lighting': {'fill': 0.7, 'exposure_mul': 1.15}} 
- S08 ['face_too_dark'] -> {'lighting': {'fill': 0.7, 'exposure_mul': 1.15}} 
- S09 ['face_too_dark'] -> {'lighting': {'fill': 0.7, 'exposure_mul': 1.15}} 
- S10 ['face_too_dark'] -> {'lighting': {'fill': 0.7, 'exposure_mul': 1.15}} 
- S14 ['face_too_dark'] -> {'lighting': {'fill': 0.7, 'exposure_mul': 1.15}} 
- S16 ['screen_text_low_contrast'] -> {'ui': {'bloom': 0.15}} 
- S18 ['face_too_dark'] -> {'lighting': {'fill': 0.7, 'exposure_mul': 1.15}} 
- S19 ['face_too_dark'] -> {'lighting': {'fill': 0.7, 'exposure_mul': 1.15}} 

## Round 1
geometry-bad shots: 0, pixel flags: 7

- S01 ['face_too_dark'] -> {'lighting': {'fill': 1.4, 'exposure_mul': 1.322}} 
- S02 ['face_too_dark'] -> {'lighting': {'fill': 1.4, 'exposure_mul': 1.322}} 
- S03 ['face_too_dark'] -> {'lighting': {'fill': 1.4, 'exposure_mul': 1.322}} 
- S04 ['face_too_dark'] -> {'lighting': {'fill': 1.4, 'exposure_mul': 1.322}} 
- S05 ['face_too_dark'] -> {'lighting': {'fill': 1.4, 'exposure_mul': 1.322}} 
- S06 ['face_too_dark'] -> {'lighting': {'fill': 1.4, 'exposure_mul': 1.322}} 
- S11 ['face_too_dark'] -> {'lighting': {'fill': 0.7, 'exposure_mul': 1.15}} 

## Round 2
geometry-bad shots: 0, pixel flags: 4

- S01 ['face_too_dark'] -> {'lighting': {'fill': 2.1, 'exposure_mul': 1.52}} 
- S02 ['face_too_dark'] -> {'lighting': {'fill': 2.1, 'exposure_mul': 1.52}} 
- S04 ['face_too_dark'] -> {'lighting': {'fill': 2.1, 'exposure_mul': 1.52}} 
- S05 ['face_too_dark'] -> {'lighting': {'fill': 2.1, 'exposure_mul': 1.52}} 

## Round 3
geometry-bad shots: 0, pixel flags: 0


## VLM advisory (not auto-fixed unless a measurement agreed)
- S03 score 5: ['Face is not clearly visible due to low lighting', 'Overall scene darkness reduces visual clarity']
- S13 score 5: ['overall scene is too dark', 'faces lack sufficient lighting for clear expression reading']
- S16 score 4: ['No character present', 'Frame too dark for cinematic quality']
- S17 score 5: ['No character face visible', 'Low contrast and muted colors reduce clarity']
- S20 score 4: ['faces are too small and dimly lit to read expressions', 'overall scene is underexposed with low contrast']
