# FLStudioMCP Tool Map

## Transport

- Connectivity: `fl_ping`.
- Tempo/time signature: `fl_get_tempo`, `fl_set_tempo`,
  `fl_get_time_signature`, `fl_set_time_signature`.
- Playback: `fl_play`, `fl_stop`, `fl_toggle_play`, `fl_get_play_state`,
  `fl_get_song_position`, `fl_set_song_position`.

## Project, Safety, And Reports

- Project reads: `fl_get_project_state`, `fl_get_mixer_state`,
  `fl_get_channel_state`.
- Safety state: `fl_get_change_history`, `fl_take_snapshot`,
  `fl_rollback_last_change`, `fl_rollback_change`, `fl_set_dry_run`.
- Reports: `fl_project_health_report`, `fl_export_readiness_report`,
  `fl_project_dry_run_fix_plan`.

## Mixer, Routing, Bulk, And Color

- Mixer reads/writes: `fl_mixer_list_tracks`, `fl_mixer_get_track`,
  `fl_mixer_set_volume`, `fl_mixer_set_pan`, `fl_mixer_set_mute`,
  `fl_mixer_set_solo`, `fl_mixer_set_stereo_separation`,
  `fl_mixer_select_track`.
- Routing: `fl_get_routing`, `fl_get_routing_all`,
  `fl_get_channel_routing`, `fl_detect_cleanup_candidates`,
  `fl_set_route`, `fl_group_tracks`.
- Bulk: `fl_solo_tracks`, `fl_mute_tracks`, `fl_clear_mute_solo`.
- Color: `fl_set_track_color`, `fl_set_channel_color`.

## Channels, Patterns, Playlist, Arrangement

- Channels: `fl_get_channel_details`, `fl_detect_unassigned_channels`,
  `fl_set_channel_name`, `fl_set_channel_mixer_track`,
  `fl_assign_channel_to_free_mixer_track`.
- Step sequencer: `fl_channel_get_grid`, `fl_channel_set_grid_bit`,
  `fl_channel_set_step_param`, `fl_channel_set_steps`,
  `fl_channel_clear_grid`.
- Patterns and playlist: `fl_pattern_list`, `fl_pattern_get`,
  `fl_pattern_get_length`, `fl_pattern_select`, `fl_pattern_rename`,
  `fl_pattern_set_color`, `fl_pattern_set_length`, `fl_pattern_find_empty`,
  `fl_playlist_list_tracks`, `fl_playlist_get_track`,
  `fl_playlist_set_mute`, `fl_playlist_set_solo`, `fl_playlist_set_name`,
  `fl_playlist_set_color`, `fl_playlist_select_track`.
- Arrangement primitives: `fl_arrange_new_pattern`,
  `fl_arrange_select_channel`, `fl_arrange_clone_pattern`,
  `fl_arrange_add_marker`.

## Piano Roll, Composition, Audio, Export

- Piano Roll: `fl_piano_write_notes`, `fl_piano_write_chord`,
  `fl_piano_clear`, `fl_piano_quantize`, `fl_piano_transpose`,
  `fl_piano_duplicate`, `fl_piano_velocity_ramp`, `fl_piano_add_marker`,
  `fl_piano_add_time_signature_marker`, `fl_piano_clear_markers`,
  `fl_piano_get_notes`.
- Scale composition: `fl_scale_list`, `fl_scale_get`,
  `fl_write_raga_melody`, `fl_write_raga_chords`.
- Audio analysis: `fl_analyze_audio`, `fl_extract_melody`.
- MIDI file export: `fl_export_midi`.

## Plugins, Effects, Mixing

- Plugin reads/writes: `fl_plugin_list`, `fl_plugin_get_params`,
  `fl_plugin_list_params`, `fl_plugin_get_param`, `fl_plugin_set_param`,
  `fl_plugin_get_preset_name`, `fl_plugin_next_preset`,
  `fl_plugin_prev_preset`.
- Effects and EQ: `fl_effect_get_slot`, `fl_effect_list_slots`,
  `fl_effect_set_slot_mix`, `fl_effect_get_track_slots_enabled`,
  `fl_effect_set_track_slots_enabled`, `fl_effect_set_slot_enabled`,
  `fl_eq_get`, `fl_eq_set_band`.
- Intent tools for already-loaded plugins: `fl_apply_eq_intent`,
  `fl_apply_reverb_intent`, `fl_apply_delay_intent`,
  `fl_apply_compression_intent`, `fl_get_track_level`.
- Planning and libraries: `fl_review_mix`, `fl_apply_mix_adjustment`,
  `fl_mix_watch_start`, `fl_mix_watch_status`, `fl_mix_watch_stop`,
  `fl_gain_stage`, `fl_reference_match`, `fl_list_chains`,
  `fl_list_installed_plugins`, `fl_setup_chain`, `fl_list_presets`,
  `fl_suggest_preset`.
