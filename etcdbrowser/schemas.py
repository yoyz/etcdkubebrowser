# Copyright (c) 2026
#
# Kubernetes / OpenShift protobuf field-number schemas used to decode the
# ``raw`` payload inside the ``k8s\x00`` runtime.Unknown envelope.
#
# Field numbers follow k8s.io/api + k8s.io/apimachinery generated.proto.
# Types use the tuples understood by decode.py:
#   ("str",), ("bytes",), ("bool",), ("int32",), ("int64",), ("float",),
#   ("any",)            -> generic rendering
#   ("json",)           -> try JSON parse, else keep string
#   ("msg", NAME|None)  -> nested message (None = generic decode)
#   ("rep", TYPE)       -> repeated field of TYPE
#   ("map", ("str"|"bytes",)) -> map<string, ...>

META = {1: ("name", ("str",)),
        2: ("generateName", ("str",)),
        3: ("namespace", ("str",)),
        4: ("selfLink", ("str",)),
        5: ("uid", ("str",)),
        6: ("resourceVersion", ("str",)),
        7: ("generation", ("int64",)),
        8: ("creationTimestamp", ("str",)),
        9: ("deletionTimestamp", ("str",)),
        10: ("deletionGracePeriodSeconds", ("int64",)),
        11: ("labels", ("map", ("str",))),
        12: ("annotations", ("map", ("str",))),
        13: ("ownerReferences", ("rep", ("msg", "OwnerReference"))),
        14: ("finalizers", ("rep", ("str",))),
        15: ("clusterName", ("str",)),
        17: ("managedFields", ("rep", ("msg", "ManagedFieldsEntry")))}

OWNER_REF = {1: ("apiVersion", ("str",)), 2: ("kind", ("str",)), 3: ("name", ("str",)),
             4: ("uid", ("str",)), 5: ("controller", ("bool",)),
             6: ("blockOwnerDeletion", ("bool",))}

MANAGED_FIELDS = {1: ("manager", ("str",)), 2: ("operation", ("str",)),
                  3: ("apiVersion", ("str",)), 4: ("time", ("str",)),
                  5: ("fieldsType", ("str",)), 6: ("fieldsV1", ("any",)),
                  7: ("subresource", ("str",))}

OBJ_REF = {1: ("kind", ("str",)), 2: ("namespace", ("str",)), 3: ("name", ("str",)),
           4: ("uid", ("str",)), 5: ("apiVersion", ("str",)),
           6: ("resourceVersion", ("str",)), 7: ("fieldPath", ("str",))}

LOCAL_OBJ_REF = {1: ("name", ("str",))}

LABEL_SELECTOR = {1: ("matchLabels", ("map", ("str",))),
                  2: ("matchExpressions", ("rep", ("msg", "LabelSelectorRequirement")))}

LABEL_SEL_REQ = {1: ("key", ("str",)), 2: ("operator", ("str",)),
                 3: ("values", ("rep", ("str",)))}

# ----------------------------------------------------------------- core ----

CONFIGMAP = {1: ("metadata", ("msg", "ObjectMeta")),
             2: ("data", ("map", ("str",))),
             3: ("binaryData", ("map", ("bytes",))),
             4: ("immutable", ("bool",))}

SECRET = {1: ("metadata", ("msg", "ObjectMeta")),
          2: ("data", ("map", ("bytes",))),
          3: ("type", ("str",)),
          4: ("stringData", ("map", ("str",))),
          5: ("immutable", ("bool",))}

SERVICE_ACCOUNT = {1: ("metadata", ("msg", "ObjectMeta")),
                   2: ("secrets", ("rep", ("msg", "ObjectReference"))),
                   3: ("imagePullSecrets", ("rep", ("msg", "LocalObjectReference"))),
                   4: ("automountServiceAccountToken", ("bool",))}

SERVICE_SPEC = {1: ("ports", ("rep", ("msg", "ServicePort"))),
                2: ("selector", ("map", ("str",))),
                3: ("clusterIP", ("str",)),
                4: ("type", ("str",)),
                5: ("externalIPs", ("rep", ("str",))),
                7: ("sessionAffinity", ("str",)),
                8: ("loadBalancerIP", ("str",)),
                9: ("loadBalancerSourceRanges", ("rep", ("str",))),
                10: ("externalName", ("str",)),
                11: ("externalTrafficPolicy", ("str",)),
                12: ("healthCheckNodePort", ("int32",)),
                13: ("publishNotReadyAddresses", ("bool",)),
                14: ("sessionAffinityConfig", ("any",)),
                17: ("ipFamilyPolicy", ("str",)),
                18: ("clusterIPs", ("rep", ("str",))),
                19: ("ipFamilies", ("rep", ("str",))),
                20: ("allocateLoadBalancerNodePorts", ("bool",)),
                21: ("loadBalancerClass", ("str",)),
                22: ("internalTrafficPolicy", ("str",))}

SERVICE_PORT = {1: ("name", ("str",)), 2: ("protocol", ("str",)),
                3: ("port", ("int32",)), 4: ("targetPort", ("any",)),
                5: ("nodePort", ("int32",))}

SERVICE = {1: ("metadata", ("msg", "ObjectMeta")),
           2: ("spec", ("msg", "ServiceSpec")),
           3: ("status", ("msg", None))}

NAMESPACE = {1: ("metadata", ("msg", "ObjectMeta")),
             2: ("spec", ("msg", None)),
             3: ("status", ("msg", None))}

NODE = {1: ("metadata", ("msg", "ObjectMeta")),
        2: ("spec", ("msg", None)),
        3: ("status", ("msg", None))}

CONTAINER = {1: ("name", ("str",)), 2: ("image", ("str",)),
             3: ("command", ("rep", ("str",))),
             4: ("args", ("rep", ("str",))),
             5: ("workingDir", ("str",)),
             6: ("ports", ("rep", ("msg", None))),
             7: ("env", ("rep", ("msg", None))),
             8: ("resources", ("msg", None)),
             9: ("volumeMounts", ("rep", ("msg", None))),
             10: ("livenessProbe", ("msg", None)),
             11: ("readinessProbe", ("msg", None)),
             12: ("lifecycle", ("msg", None)),
             13: ("terminationMessagePath", ("str",)),
             14: ("imagePullPolicy", ("str",)),
             15: ("securityContext", ("msg", None)),
             16: ("stdin", ("bool",)),
             17: ("stdinOnce", ("bool",)),
             18: ("tty", ("bool",)),
             19: ("envFrom", ("rep", ("msg", None))),
             20: ("terminationMessagePolicy", ("str",)),
             21: ("volumeDevices", ("rep", ("msg", None))),
             22: ("startupProbe", ("msg", None)),
             24: ("restartPolicy", ("str",))}

POD_SPEC = {1: ("volumes", ("rep", ("msg", None))),
            2: ("containers", ("rep", ("msg", "Container"))),
            3: ("restartPolicy", ("str",)),
            4: ("terminationGracePeriodSeconds", ("int64",)),
            5: ("activeDeadlineSeconds", ("int64",)),
            6: ("dnsPolicy", ("str",)),
            7: ("nodeSelector", ("map", ("str",))),
            8: ("serviceAccountName", ("str",)),
            9: ("serviceAccount", ("str",)),
            10: ("nodeName", ("str",)),
            11: ("hostNetwork", ("bool",)),
            12: ("hostPID", ("bool",)),
            13: ("hostIPC", ("bool",)),
            14: ("securityContext", ("msg", None)),
            15: ("imagePullSecrets", ("rep", ("msg", "LocalObjectReference"))),
            16: ("hostname", ("str",)),
            17: ("subdomain", ("str",)),
            18: ("affinity", ("msg", None)),
            19: ("schedulerName", ("str",)),
            20: ("initContainers", ("rep", ("msg", "Container"))),
            21: ("automountServiceAccountToken", ("bool",)),
            22: ("tolerations", ("rep", ("msg", None))),
            24: ("priorityClassName", ("str",)),
            27: ("shareProcessNamespace", ("bool",)),
            29: ("runtimeClassName", ("str",))}

POD_TEMPLATE_SPEC = {1: ("metadata", ("msg", "ObjectMeta")),
                     2: ("spec", ("msg", "PodSpec"))}

POD = {1: ("metadata", ("msg", "ObjectMeta")),
       2: ("spec", ("msg", "PodSpec")),
       3: ("status", ("msg", None))}

ENDPOINT_SLICE = {1: ("metadata", ("msg", "ObjectMeta")),
                  2: ("addressType", ("str",)),
                  3: ("endpoints", ("rep", ("msg", None))),
                  4: ("ports", ("rep", ("msg", None)))}

ENDPOINTS = {1: ("metadata", ("msg", "ObjectMeta")),
             2: ("subsets", ("rep", ("msg", None)))}

# ------------------------------------------------------------------ apps ----

DEPLOYMENT_SPEC = {1: ("replicas", ("int32",)),
                   2: ("selector", ("msg", "LabelSelector")),
                   3: ("template", ("msg", "PodTemplateSpec")),
                   4: ("strategy", ("msg", None)),
                   5: ("minReadySeconds", ("int32",)),
                   6: ("revisionHistoryLimit", ("int32",)),
                   7: ("paused", ("bool",)),
                   8: ("progressDeadlineSeconds", ("int32",))}

DEPLOYMENT = {1: ("metadata", ("msg", "ObjectMeta")),
              2: ("spec", ("msg", "DeploymentSpec")),
              3: ("status", ("msg", None))}

REPLICASET = {1: ("metadata", ("msg", "ObjectMeta")),
              2: ("spec", ("msg", None)),
              3: ("status", ("msg", None))}

STATEFULSET = {1: ("metadata", ("msg", "ObjectMeta")),
               2: ("spec", ("msg", None)),
               3: ("status", ("msg", None))}

DAEMONSET = {1: ("metadata", ("msg", "ObjectMeta")),
             2: ("spec", ("msg", None)),
             3: ("status", ("msg", None))}

# ----------------------------------------------------------------- batch ----

JOB = {1: ("metadata", ("msg", "ObjectMeta")),
       2: ("spec", ("msg", None)),
       3: ("status", ("msg", None))}

CRONJOB = {1: ("metadata", ("msg", "ObjectMeta")),
           2: ("spec", ("msg", None)),
           3: ("status", ("msg", None))}

REPLICATION_CONTROLLER = {1: ("metadata", ("msg", "ObjectMeta")),
                          2: ("spec", ("msg", None)),
                          3: ("status", ("msg", None))}

# ------------------------------------------------------------------ rbac ----

POLICY_RULE = {1: ("verbs", ("rep", ("str",))),
               2: ("apiGroups", ("rep", ("str",))),
               3: ("resources", ("rep", ("str",))),
               4: ("resourceNames", ("rep", ("str",))),
               5: ("nonResourceURLs", ("rep", ("str",)))}

ROLE = {1: ("metadata", ("msg", "ObjectMeta")),
        2: ("rules", ("rep", ("msg", "PolicyRule")))}

CLUSTER_ROLE = {1: ("metadata", ("msg", "ObjectMeta")),
                2: ("rules", ("rep", ("msg", "PolicyRule"))),
                3: ("aggregationRule", ("msg", None))}

SUBJECT = {1: ("kind", ("str",)), 2: ("apiGroup", ("str",)),
           3: ("name", ("str",)), 4: ("namespace", ("str",))}

ROLE_REF = {1: ("apiGroup", ("str",)), 2: ("kind", ("str",)), 3: ("name", ("str",))}

ROLE_BINDING = {1: ("metadata", ("msg", "ObjectMeta")),
                2: ("subjects", ("rep", ("msg", "Subject"))),
                3: ("roleRef", ("msg", "RoleRef"))}

CLUSTER_ROLE_BINDING = {1: ("metadata", ("msg", "ObjectMeta")),
                        2: ("subjects", ("rep", ("msg", "Subject"))),
                        3: ("roleRef", ("msg", "RoleRef"))}

# ------------------------------------------------------------ storage/csi ----

PV = {1: ("metadata", ("msg", "ObjectMeta")),
      2: ("spec", ("msg", None)),
      3: ("status", ("msg", None))}

PVC = {1: ("metadata", ("msg", "ObjectMeta")),
       2: ("spec", ("msg", None)),
       3: ("status", ("msg", None))}

STORAGE_CLASS = {1: ("metadata", ("msg", "ObjectMeta")),
                 2: ("provisioner", ("str",)),
                 3: ("parameters", ("map", ("str",))),
                 4: ("reclaimPolicy", ("str",)),
                 5: ("mountOptions", ("rep", ("str",))),
                 6: ("allowVolumeExpansion", ("bool",)),
                 7: ("volumeBindingMode", ("str",)),
                 8: ("allowedTopologies", ("rep", ("msg", None)))}

# ------------------------------------------------------------ coordination --

LEASE_SPEC = {1: ("holderIdentity", ("str",)),
              2: ("leaseDurationSeconds", ("int32",)),
              3: ("acquireTime", ("str",)),
              4: ("renewTime", ("str",)),
              5: ("leaseTransitions", ("int32",)),
              6: ("preferredHolder", ("str",)),
              7: ("strategy", ("str",))}

LEASE = {1: ("metadata", ("msg", "ObjectMeta")),
         2: ("spec", ("msg", "LeaseSpec"))}

# ----------------------------------------------------------------- events --

EVENT = {1: ("metadata", ("msg", "ObjectMeta")),
         2: ("involvedObject", ("msg", "ObjectReference")),
         3: ("reason", ("str",)),
         4: ("message", ("str",)),
         5: ("source", ("msg", None)),
         6: ("firstTimestamp", ("str",)),
         7: ("lastTimestamp", ("str",)),
         8: ("count", ("int32",)),
         9: ("type", ("str",)),
         10: ("eventTime", ("str",)),
         11: ("series", ("msg", None)),
         12: ("action", ("str",)),
         13: ("related", ("msg", "ObjectReference")),
         14: ("reportingController", ("str",)),
         15: ("reportingInstance", ("str",))}

# ------------------------------------------------------------ networking ---

INGRESS = {1: ("metadata", ("msg", "ObjectMeta")),
           2: ("spec", ("msg", None)),
           3: ("status", ("msg", None))}

NETWORK_POLICY = {1: ("metadata", ("msg", "ObjectMeta")),
                  2: ("spec", ("msg", None)),
                  3: ("status", ("msg", None))}

INGRESS_CLASS = {1: ("metadata", ("msg", "ObjectMeta")),
                 2: ("spec", ("msg", None))}

# ------------------------------------------------------------ scheduling ---

PRIORITY_CLASS = {1: ("metadata", ("msg", "ObjectMeta")),
                  2: ("value", ("int32",)),
                  3: ("globalDefault", ("bool",)),
                  4: ("description", ("str",)),
                  5: ("preemptionPolicy", ("str",))}

# ------------------------------------------------------------ misc kinds ---

APISERVICE = {1: ("metadata", ("msg", "ObjectMeta")),
              2: ("spec", ("msg", None)),
              3: ("status", ("msg", None))}

CUSTOM_RESOURCE_DEFINITION = {1: ("metadata", ("msg", "ObjectMeta")),
                              2: ("spec", ("msg", None)),
                              3: ("status", ("msg", None))}

CONTROLLER_REVISION = {1: ("metadata", ("msg", "ObjectMeta")),
                       2: ("data", ("any",)),
                       3: ("revision", ("int64",))}

GENERIC = {1: ("metadata", ("msg", "ObjectMeta")),
           2: ("spec", ("msg", None)),
           3: ("status", ("msg", None))}

SCHEMAS: dict[str, dict] = {
    # helper / embedded messages
    "ObjectMeta": META,
    "OwnerReference": OWNER_REF,
    "ManagedFieldsEntry": MANAGED_FIELDS,
    "ObjectReference": OBJ_REF,
    "LocalObjectReference": LOCAL_OBJ_REF,
    "LabelSelector": LABEL_SELECTOR,
    "LabelSelectorRequirement": LABEL_SEL_REQ,
    "ServicePort": SERVICE_PORT,
    "PodSpec": POD_SPEC,
    "PodTemplateSpec": POD_TEMPLATE_SPEC,
    "Container": CONTAINER,
    "DeploymentSpec": DEPLOYMENT_SPEC,
    "PolicyRule": POLICY_RULE,
    "Subject": SUBJECT,
    "RoleRef": ROLE_REF,
    "LeaseSpec": LEASE_SPEC,
    # kinds
    "ConfigMap": CONFIGMAP,
    "Secret": SECRET,
    "ServiceAccount": SERVICE_ACCOUNT,
    "Service": SERVICE,
    "Namespace": NAMESPACE,
    "Node": NODE,
    "Pod": POD,
    "Deployment": DEPLOYMENT,
    "ReplicaSet": REPLICASET,
    "StatefulSet": STATEFULSET,
    "DaemonSet": DAEMONSET,
    "Job": JOB,
    "CronJob": CRONJOB,
    "ReplicationController": REPLICATION_CONTROLLER,
    "Role": ROLE,
    "ClusterRole": CLUSTER_ROLE,
    "RoleBinding": ROLE_BINDING,
    "ClusterRoleBinding": CLUSTER_ROLE_BINDING,
    "PersistentVolume": PV,
    "PersistentVolumeClaim": PVC,
    "StorageClass": STORAGE_CLASS,
    "Lease": LEASE,
    "Event": EVENT,
    "Ingress": INGRESS,
    "NetworkPolicy": NETWORK_POLICY,
    "IngressClass": INGRESS_CLASS,
    "PriorityClass": PRIORITY_CLASS,
    "APIService": APISERVICE,
    "CustomResourceDefinition": CUSTOM_RESOURCE_DEFINITION,
    "ControllerRevision": CONTROLLER_REVISION,
    "Endpoints": ENDPOINTS,
    "EndpointSlice": ENDPOINT_SLICE,
}

# OpenShift native types use the same metadata/spec/status shape; field
# numbers for their spec/status are handled generically.
for _kind in ("Route", "Image", "ImageStream", "OAuthAccessToken", "OAuthAuthorizeToken",
              "OAuthClient", "OAuthClientAuthorization", "ImageStreamTag",
              "ImageStreamImage", "Config", "FeatureGate", "ClusterOperator",
              "Machine", "MachineSet", "MachineConfig", "Infrastructure"):
    SCHEMAS.setdefault(_kind, GENERIC)


def for_kind(kind: str, api_version: str = "") -> dict | None:
    return SCHEMAS.get(kind)
