# Generic Resource-Kind Mutation Tool Package

- Three tools (`rancher_resource_set_labels`, `rancher_resource_set_annotations`,
  `rancher_resource_delete`) dispatch across every `generic_kind` resource
  family via a closed `resource_kind` enum, generated into `_generated_kinds.py`
  from `catalog/curated_tools/*.yml`. Never hand-edit `_generated_kinds.py` —
  change a descriptor's `generic_kind` block and run `make codegen`.
- Keep routing/safety logic in `shared.py`; keep the three tools themselves
  thin and mechanically similar to each other and to the codegen'd
  per-resource patch/delete tools they replace.
- `resource_kind` must always resolve through the generated registry —
  never hardcode a per-kind branch here.
