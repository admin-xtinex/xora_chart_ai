# Pattern Repository

Place high-quality reference chart images for each pattern here.

```
patterns/
  bull_flag/
    example1.png
    example2.png
    ...
  bear_flag/
  double_bottom/
  ...
```

Each enabled pattern in `config/patterns.yaml` maps to a folder of the same name.

Phase 2 uses the educational catalog in `data/patterns.json` + heuristic matching.
Phase 3 will score live candles against these reference images (vision / embeddings).

Target: ~10 examples per pattern.
