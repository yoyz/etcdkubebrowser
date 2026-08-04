# Decoding an etcd entry — worked example

This document explains, on a real entry from the bundled snapshot, exactly how
`etcdbrowser` turns the raw bytes stored in etcd into the readable object you
see in the browser — and where the "schema" that makes it possible comes from.

---

## 1. The big picture

A kube-apiserver stores a Kubernetes object in etcd as a single value at a key
such as `/kubernetes.io/secrets/kube-system/kube-cloud-cfg`. The value is **not
plain JSON** for built-in types. It is a protobuf blob with this shape:

```
k8s\x00                      4-byte magic marker ("k8s" + NUL)
+ runtime.Unknown message    the "envelope"
    1  TypeMeta             {1: apiVersion, 2: kind}     (a.k.a. typeMeta)
    2  bytes raw            the object, k8s-protobuf serialized
    3  string contentEncoding
    4  string contentType
```

`etcdbrowser` only has to deal with the protobuf wire format and the field
numbers of the inner object. CRDs (and a few other values) are stored as plain
JSON and parsed directly; opaque bytes are shown base64-encoded. Nothing is
ever dropped: any field whose number is not in our schema is preserved under an
`f<number>` key.

---

## 2. Fetching a real entry with etcdctl

`open` starts a local etcd serving the restored snapshot on
`127.0.0.1:22379`. Fetch the value with `etcdctl`:

```sh
etcdctl --endpoints http://127.0.0.1:22379 \
        get /kubernetes.io/secrets/kube-system/kube-cloud-cfg \
        --print-value-only
```

A hexdump of the 238-byte value (`xxd`) is shown in section 4. This entry was
chosen because it is small but contains every interesting feature: the
`k8s\x00` magic, the envelope, the `ObjectMeta` (name / namespace / uid /
creationTimestamp / managedFields), a map, and a scalar.

---

## 3. Step-by-step decode of that entry

### 3.1 The 4-byte magic

Bytes `0x00..0x03` are `6b 38 73 00` = ASCII `k8s` followed by `\x00`. If a
value does **not** start with these bytes, `decode_value()` treats it as JSON
(starts with `{`/`[`) or raw bytes.

### 3.2 The `runtime.Unknown` envelope

The payload after the magic is a protobuf message with four fields:

| offset | tag (field, wire) | length | meaning | value |
| --- | --- | --- | --- | --- |
| `0x04` | `0a` = f1, LEN | 12 | `typeMeta` | nested message |
| `0x12` | `12` = f2, LEN | 213 | `raw` | the Secret object |
| `0xea` | `1a` = f3, LEN | 0 | `contentEncoding` | `""` |
| `0xec` | `22` = f4, LEN | 0 | `contentType` | `""` |

The tag byte encodes `(field_number << 3) | wire_type`. `0x0a` =
`0b0_0001_010` → field 1, wire type 2 (length-delimited). `0x12` = `0b0_0010_010`
→ field 2, wire type 2.

The `typeMeta` (offset `0x04`, 12 bytes) is itself a message:

```
0a 02 76 31    f1 apiVersion, len 2 = "v1"
12 06 53 65 63 72 65 74   f2 kind, len 6 = "Secret"
```

So `decode_k8s()` learns `apiVersion="v1"`, `kind="Secret"` and can look up the
Secret schema.

### 3.3 The inner Secret object (the `raw` payload, 213 bytes)

`decode_k8s()` hands the `raw` bytes to `decode_message(raw, schema)` where
`schema` is the Secret field map. The top level of the object:

| offset | tag | length | field (schema) | value |
| --- | --- | --- | --- | --- |
| `0x15` | `0a` f1 | 190 | `metadata` | `ObjectMeta` (see 3.4) |
| `0xd6` | `12` f2 | 10 | `data` | map entry, see below |
| `0xe2` | `1a` f3 | 6 | `type` | `"Opaque"` |

The `data` field is a `map<string, string>`. A protobuf map is a repeated
message where each entry is `{1: key, 2: value}`:

```
0a 06 63 6f 6e 66 69 67   f1 key   = "config"
12 00                     f2 value = ""
```

`decode._decode_map()` turns that into `{"config": ""}`.

### 3.4 The `ObjectMeta` (Secret.f1, 190 bytes)

`metadata` decodes against the shared `ObjectMeta` schema (`META` in
`schemas.py`):

| offset | tag | length | field | value |
| --- | --- | --- | --- | --- |
| `0x18` | `0a` f1 | 14 | `name` | `"kube-cloud-cfg"` |
| `0x28` | `12` f2 | 0 | `generateName` | `""` |
| `0x2a` | `1a` f3 | 11 | `namespace` | `"kube-system"` |
| `0x37` | `22` f4 | 0 | `selfLink` | `""` |
| `0x39` | `2a` f5 | 36 | `uid` | `"9b9d93e4-ba44-4966-bd9f-be4ca226d516"` |
| `0x5f` | `32` f6 | 0 | `resourceVersion` | `""` |
| `0x61` | `38` f7 | varint | `generation` | `0` |
| `0x63` | `42` f8 | 8 | `creationTimestamp` | `Time` message |
| `0x6d` | `8a 01` f17 | 102 | `managedFields` | 1 × `ManagedFieldsEntry` |

Note two non-obvious points:

- `creationTimestamp` (and `deletionTimestamp`, and `managedFields[].time`)
  are **not** strings. They are a `Time` message `{1: seconds, 2: nanos}`:
  `08 db fa e1 cc 06 10 00` → `seconds=1771601243`, `nanos=0`.
- `managedFields` is field **17**, and inside a `ManagedFieldsEntry` the
  numbering is `1 manager, 2 operation, 3 apiVersion, 4 time, 6 fieldsType,
  7 fieldsV1, 8 subresource` — note there is **no field 5**, and `fieldsV1`
  is itself a message `{1: raw}` whose payload is a JSON string.

### 3.5 The `ManagedFieldsEntry` (ObjectMeta.f17, 102 bytes)

| offset | tag | length | field | value |
| --- | --- | --- | --- | --- |
| `0x70` | `0a` f1 | 17 | `manager` | `"cluster-bootstrap"` |
| `0x83` | `12` f2 | 6 | `operation` | `"Update"` |
| `0x8b` | `1a` f3 | 2 | `apiVersion` | `"v1"` |
| `0x8f` | `22` f4 | 8 | `time` | `Time {seconds=1771601243, nanos=0}` |
| `0x99` | `32` f6 | 8 | `fieldsType` | `"FieldsV1"` |
| `0xa3` | `3a` f7 | 47 | `fieldsV1` | `FieldsV1 {1: raw}` |
| `0xd4` | `42` f8 | 0 | `subresource` | `""` |

`fieldsV1` (offset `0xa3`) is `3a 2f` = field 7, length 47. Its payload is a
`FieldsV1` message `{1: raw}`: `0a 2d` = field 1, length 45, and the JSON
document itself spans `0xa7..0xd4`:
`{"f:data":{".":{},"f:config":{}},"f:type":{}}` — the structured-merge
ownership tree, decoded with the `("json",)` type.

### 3.6 The result

Putting it all together, `decode.decode_value()` returns:

```json
{
  "format": "k8s",
  "apiVersion": "v1",
  "kind": "Secret",
  "object": {
    "metadata": {
      "name": "kube-cloud-cfg",
      "namespace": "kube-system",
      "uid": "9b9d93e4-ba44-4966-bd9f-be4ca226d516",
      "creationTimestamp": {"seconds": 1771601243, "nanos": 0},
      "managedFields": [
        {"manager": "cluster-bootstrap", "operation": "Update",
         "apiVersion": "v1", "time": {"seconds": 1771601243, "nanos": 0},
         "fieldsType": "FieldsV1", "fieldsV1": {"raw": {"f:data": {".": {}, "f:config": {}}, "f:type": {}}},
         "subresource": ""}
      ]
    },
    "data": {"config": ""},
    "type": "Opaque"
  }
}
```

This is exactly what the browser's value pane shows (as JSON or YAML, toggled
with `y`), and what `E` exports.

---

## 4. Files in the tree involved in decoding

| file | responsibility |
| --- | --- |
| `etcdbrowser.py` | CLI. `open` restores + serves the snapshot; `browse`/`export`/`verify` talk to it via `KVClient`. |
| `etcdbrowser/backend.py` | `KVClient` fetches a value from etcd's HTTP/JSON v3 gateway (`get()`), the tool never reads etcd's on-disk format. |
| `etcdbrowser/decode.py` | the whole pipeline: `decode_value()` → `decode_k8s()` → `decode_message()`, plus the protobuf wire parser `read_varint()` / `parse_fields()` and the lossless generic fallback (`generic_message`, `generic_value`, `_decode_map`). |
| `etcdbrowser/schemas.py` | the field-number schemas (`META`, `SECRET`, `POD`, `OWNER_REF`, `MANAGED_FIELDS`, `TIME`, …) and the `for_kind(kind, apiVersion)` resolver. This is the file that must match the source of truth (see §5). |
| `etcdbrowser/objects.py` | builds the namespace→kind→name tree from decoded `metadata` (does not re-decode). |
| `etcdbrowser/yamlout.py` | renders decoded values as YAML for the value pane and exports. |
| `etcdbrowser/verify.py` | `verify` command — re-parses raw wire data against the schemas and reports unknown fields / wire-type mismatches, so a drift from §5 can be detected instead of silently producing `f<N>`. |
| `etcdbrowser/tui.py` | the curses browser; calls `decode.decode_value()` lazily per leaf. |

Data flow: `KVClient.get(key)` → bytes → `decode.decode_value(bytes)` →
`{"format": "k8s", "apiVersion", "kind", "object": {...}}` → value pane /
object tree / export.

To inspect what a given key decodes to without the TUI:

```sh
python3 -S etcdbrowser.py export /kubernetes.io/secrets/kube-system/kube-cloud-cfg out.json
python3 -S etcdbrowser.py verify          # does every field match the schemas?
```

---

## 5. Source of truth on the internet

The field numbers used in `schemas.py` are the **canonical Kubernetes
protobuf definitions**, and OpenShift does not deviate from them (its
`openshift/kubernetes` fork is field-identical to upstream). The authoritative
sources, in priority order:

1. **`k8s.io/apimachinery` — `pkg/apis/meta/v1/generated.proto`** — defines
   the envelope types shared by every object: `ObjectMeta`, `OwnerReference`,
   `ManagedFieldsEntry`, `FieldsV1`, `Time`, `MicroTime`, `LabelSelector`.
   This is where the non-obvious numbers come from:
   <https://github.com/kubernetes/apimachinery/blob/master/pkg/apis/meta/v1/generated.proto>

2. **`k8s.io/api` — `*/generated.proto`** — one file per API group/version for
   the built-in resources (core `v1`, `apps/v1`, `rbac.authorization.k8s.io/v1`,
   `storage/v1`, …), e.g.
   <https://github.com/kubernetes/api/blob/master/core/v1/generated.proto>
   (Secret, Pod, Service, …) and
   <https://github.com/kubernetes/api/blob/master/storage/v1/generated.proto>
   (CSIStorageCapacity, …).

3. **`openshift/api` — `*/generated.proto`** — OpenShift-native kinds
   (Image, OAuthClient, OAuthAccessToken, Route, …):
   <https://github.com/openshift/api/tree/master/image/v1> and
   <https://github.com/openshift/api/tree/master/oauth/v1>.

4. **`openshift/kubernetes` fork** — where the OpenShift distribution of the
   apiserver lives; its `generated.proto` files are field-identical to the
   upstream ones above:
   <https://github.com/openshift/kubernetes/tree/master/staging/src/k8s.io/apimachinery>

Verification workflow: the field numbers in `schemas.py` were checked against
both the proto sources above **and** the actual wire data of the bundled
snapshot (the `verify` command encodes that check). If you ever bring in a
snapshot from a different apiserver, run `python3 -S etcdbrowser.py verify` —
it reports any field numbers or wire types the schemas do not explain, rather
than silently emitting `f<number>` keys.

> Historical note: earlier versions of this project's schemas were simply
> wrong (e.g. `OwnerReference` was declared `1=apiVersion/2=kind/…`, whereas
> the canonical layout is `1=kind/3=name/4=uid/5=apiVersion/6=controller/
> 7=blockOwnerDeletion`, and `creationTimestamp` was typed as a plain string
> instead of the `Time` message). That was a bug in the schemas — not an
> OpenShift serialization difference.
