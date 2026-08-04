# Copyright (c) 2026
#
# Kubernetes / OpenShift protobuf field-number schemas used to decode the
# ``raw`` payload inside the ``k8s\x00`` runtime.Unknown envelope.
#
# Field numbers in this file follow the canonical k8s.io/api +
# k8s.io/apimachinery + openshift/api generated.proto (verified against the
# wire data of the bundled snapshot and against upstream sources).
#
# Coverage: ObjectMeta plus the spec/status of the common kinds — Pod, Node,
# Service, Deployment, ReplicaSet, StatefulSet, DaemonSet, Job, CronJob, PV,
# PVC, PDB, Namespace, NetworkPolicy, IngressClass, ResourceQuota, LimitRange,
# CSIDriver/CSINode, IPAddress, ServiceCIDR, webhook configs, FlowSchema,
# PriorityLevelConfiguration, ValidatingAdmissionPolicy(+Binding), and the
# OpenShift kinds Route, Image, ImageStream, OAuthClient, OAuthAccessToken,
# CSIStorageCapacity.
#
# NOTE: earlier versions of these schemas were wrong for several meta types
# (e.g. OwnerReference was declared 1=apiVersion/2=kind/3=name/4=uid/5=bool,
# but canonical has 1=kind/3=name/4=uid/5=apiVersion/6=controller/7=bool).
# The snapshot is *not* an OpenShift-fork quirk: the openshift/kubernetes
# generated.proto is field-identical to upstream. The schemas are canonical.
#
# Types use the tuples understood by decode.py:
#   ("str",), ("bytes",), ("bool",), ("int32",), ("int64",), ("float",),
#   ("any",)            -> generic rendering
#   ("json",)           -> try JSON parse, else keep string
#   ("msg", NAME|None)  -> nested message (None = generic decode)
#   ("rep", TYPE)       -> repeated field of TYPE
#   ("map", ("str"|"bytes",)) -> map<string, ...>

TIME = {1: ("seconds", ("int64",)), 2: ("nanos", ("int32",))}

META = {1: ("name", ("str",)),
        2: ("generateName", ("str",)),
        3: ("namespace", ("str",)),
        4: ("selfLink", ("str",)),
        5: ("uid", ("str",)),
        6: ("resourceVersion", ("str",)),
        7: ("generation", ("int64",)),
        8: ("creationTimestamp", ("msg", "Time")),
        9: ("deletionTimestamp", ("msg", "Time")),
        10: ("deletionGracePeriodSeconds", ("int64",)),
        11: ("labels", ("map", ("str",))),
        12: ("annotations", ("map", ("str",))),
        13: ("ownerReferences", ("rep", ("msg", "OwnerReference"))),
        14: ("finalizers", ("rep", ("str",))),
        15: ("clusterName", ("str",)),
        17: ("managedFields", ("rep", ("msg", "ManagedFieldsEntry")))}

OWNER_REF = {1: ("kind", ("str",)),
             3: ("name", ("str",)),
             4: ("uid", ("str",)),
             5: ("apiVersion", ("str",)),
             6: ("controller", ("bool",)),
             7: ("blockOwnerDeletion", ("bool",))}

FIELDS_V1 = {1: ("raw", ("json",))}

MANAGED_FIELDS = {1: ("manager", ("str",)), 2: ("operation", ("str",)),
                  3: ("apiVersion", ("str",)), 4: ("time", ("msg", "Time")),
                  6: ("fieldsType", ("str",)), 7: ("fieldsV1", ("msg", "FieldsV1")),
                  8: ("subresource", ("str",))}

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

SERVICE_STATUS = {1: ("loadBalancer", ("msg", None)),
                  2: ("conditions", ("rep", ("msg", None)))}

SERVICE = {1: ("metadata", ("msg", "ObjectMeta")),
           2: ("spec", ("msg", "ServiceSpec")),
           3: ("status", ("msg", "ServiceStatus"))}

NAMESPACE_SPEC = {1: ("finalizers", ("rep", ("str",)))}

NAMESPACE_STATUS = {1: ("phase", ("str",)),
                    2: ("conditions", ("rep", ("msg", None)))}

NAMESPACE = {1: ("metadata", ("msg", "ObjectMeta")),
             2: ("spec", ("msg", "NamespaceSpec")),
             3: ("status", ("msg", "NamespaceStatus"))}

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
            23: ("hostAliases", ("rep", ("msg", None))),
            24: ("priorityClassName", ("str",)),
            25: ("priority", ("int32",)),
            26: ("dnsConfig", ("msg", None)),
            27: ("shareProcessNamespace", ("bool",)),
            28: ("readinessGates", ("rep", ("msg", None))),
            29: ("runtimeClassName", ("str",)),
            30: ("enableServiceLinks", ("bool",)),
            31: ("preemptionPolicy", ("str",)),
            32: ("overhead", ("map", ("str",))),
            33: ("topologySpreadConstraints", ("rep", ("msg", None))),
            35: ("setHostnameAsFQDN", ("bool",)),
            36: ("os", ("msg", None)),
            37: ("hostUsers", ("bool",)),
            38: ("schedulingGates", ("rep", ("msg", None))),
            39: ("resourceClaims", ("rep", ("msg", None))),
            40: ("resources", ("msg", None))}

POD_TEMPLATE_SPEC = {1: ("metadata", ("msg", "ObjectMeta")),
                     2: ("spec", ("msg", "PodSpec"))}

POD_CONDITION = {1: ("type", ("str",)), 2: ("status", ("str",)),
                 3: ("lastProbeTime", ("msg", "Time")),
                 4: ("lastTransitionTime", ("msg", "Time")),
                 5: ("reason", ("str",)), 6: ("message", ("str",)),
                 7: ("observedGeneration", ("int64",))}

CONTAINER_STATE = {1: ("waiting", ("msg", None)), 2: ("running", ("msg", None)),
                   3: ("terminated", ("msg", None))}

CONTAINER_STATUS = {1: ("name", ("str",)),
                    2: ("state", ("msg", "ContainerState")),
                    3: ("lastState", ("msg", "ContainerState")),
                    4: ("ready", ("bool",)),
                    5: ("restartCount", ("int32",)),
                    6: ("image", ("str",)),
                    7: ("imageID", ("str",)),
                    8: ("containerID", ("str",)),
                    9: ("started", ("bool",)),
                    11: ("resources", ("msg", None)),
                    12: ("volumeMounts", ("rep", ("msg", None))),
                    13: ("user", ("msg", None))}

POD_STATUS = {1: ("phase", ("str",)),
              2: ("conditions", ("rep", ("msg", "PodCondition"))),
              3: ("message", ("str",)),
              4: ("reason", ("str",)),
              5: ("hostIP", ("str",)),
              6: ("podIP", ("str",)),
              7: ("startTime", ("msg", "Time")),
              8: ("containerStatuses", ("rep", ("msg", "ContainerStatus"))),
              9: ("qosClass", ("str",)),
              10: ("initContainerStatuses", ("rep", ("msg", "ContainerStatus"))),
              11: ("nominatedNodeName", ("str",)),
              12: ("podIPs", ("rep", ("msg", None))),
              13: ("ephemeralContainerStatuses", ("rep", ("msg", "ContainerStatus"))),
              14: ("resize", ("str",)),
              16: ("hostIPs", ("rep", ("msg", None))),
              17: ("observedGeneration", ("int64",))}

POD = {1: ("metadata", ("msg", "ObjectMeta")),
       2: ("spec", ("msg", "PodSpec")),
       3: ("status", ("msg", "PodStatus"))}

NODE_CONDITION = {1: ("type", ("str",)), 2: ("status", ("str",)),
                  3: ("lastHeartbeatTime", ("msg", "Time")),
                  4: ("lastTransitionTime", ("msg", "Time")),
                  5: ("reason", ("str",)), 6: ("message", ("str",))}

NODE_ADDRESS = {1: ("type", ("str",)), 2: ("address", ("str",))}

TAINT = {1: ("key", ("str",)), 2: ("value", ("str",)),
         3: ("effect", ("str",)), 4: ("timeAdded", ("msg", "Time"))}

NODE_SPEC = {1: ("podCIDR", ("str",)),
             2: ("externalID", ("str",)),
             3: ("providerID", ("str",)),
             4: ("unschedulable", ("bool",)),
             5: ("taints", ("rep", ("msg", "Taint"))),
             6: ("configSource", ("msg", None)),
             7: ("podCIDRs", ("rep", ("str",))),
             8: ("podPreemptionPolicy", ("str",))}

NODE_STATUS = {1: ("capacity", ("map", ("str",))),
               2: ("allocatable", ("map", ("str",))),
               3: ("phase", ("str",)),
               4: ("conditions", ("rep", ("msg", "NodeCondition"))),
               5: ("addresses", ("rep", ("msg", "NodeAddress"))),
               6: ("daemonEndpoints", ("msg", None)),
               7: ("nodeInfo", ("msg", None)),
               8: ("images", ("rep", ("msg", None))),
               9: ("volumesInUse", ("rep", ("str",))),
               10: ("volumesAttached", ("rep", ("msg", None))),
               11: ("config", ("msg", None)),
               12: ("runtimeHandlers", ("rep", ("msg", None))),
               13: ("features", ("msg", None)),
               14: ("declaredFeatures", ("rep", ("str",)))}

NODE = {1: ("metadata", ("msg", "ObjectMeta")),
        2: ("spec", ("msg", "NodeSpec")),
        3: ("status", ("msg", "NodeStatus"))}

PV_SPEC = {1: ("capacity", ("map", ("str",))),
           2: ("persistentVolumeSource", ("msg", None)),
           3: ("accessModes", ("rep", ("str",))),
           4: ("claimRef", ("msg", "ObjectReference")),
           5: ("persistentVolumeReclaimPolicy", ("str",)),
           6: ("storageClassName", ("str",)),
           7: ("mountOptions", ("rep", ("str",))),
           8: ("volumeMode", ("str",)),
           9: ("nodeAffinity", ("msg", None)),
           10: ("volumeAttributesClassName", ("str",))}

PV_STATUS = {1: ("phase", ("str",)), 2: ("message", ("str",)),
             3: ("reason", ("str",)), 4: ("lastPhaseTransitionTime", ("msg", "Time"))}

PV = {1: ("metadata", ("msg", "ObjectMeta")),
      2: ("spec", ("msg", "PVSpec")),
      3: ("status", ("msg", "PVStatus"))}

PVC_SPEC = {1: ("accessModes", ("rep", ("str",))),
            2: ("resources", ("msg", None)),
            3: ("volumeName", ("str",)),
            4: ("selector", ("msg", "LabelSelector")),
            5: ("storageClassName", ("str",)),
            6: ("volumeMode", ("str",)),
            7: ("dataSource", ("msg", None)),
            8: ("dataSourceRef", ("msg", None)),
            9: ("volumeAttributesClassName", ("str",))}

PVC_STATUS = {1: ("phase", ("str",)),
              2: ("accessModes", ("rep", ("str",))),
              3: ("capacity", ("map", ("str",))),
              4: ("conditions", ("rep", ("msg", None))),
              5: ("allocatedResources", ("map", ("str",))),
              7: ("allocatedResourceStatuses", ("map", ("str",)))}

PVC = {1: ("metadata", ("msg", "ObjectMeta")),
       2: ("spec", ("msg", "PVCSpec")),
       3: ("status", ("msg", "PVCStatus"))}

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
                   9: ("progressDeadlineSeconds", ("int32",))}

DEPLOYMENT_CONDITION = {1: ("type", ("str",)), 2: ("status", ("str",)),
                        4: ("reason", ("str",)), 5: ("message", ("str",)),
                        6: ("lastUpdateTime", ("msg", "Time")),
                        7: ("lastTransitionTime", ("msg", "Time"))}

DEPLOYMENT_STATUS = {1: ("observedGeneration", ("int64",)),
                     2: ("replicas", ("int32",)),
                     3: ("updatedReplicas", ("int32",)),
                     4: ("availableReplicas", ("int32",)),
                     5: ("unavailableReplicas", ("int32",)),
                     6: ("conditions", ("rep", ("msg", "DeploymentCondition"))),
                     7: ("readyReplicas", ("int32",)),
                     8: ("collisionCount", ("int32",)),
                     9: ("terminatingReplicas", ("int32",))}

DEPLOYMENT = {1: ("metadata", ("msg", "ObjectMeta")),
              2: ("spec", ("msg", "DeploymentSpec")),
              3: ("status", ("msg", "DeploymentStatus"))}

REPLICASET_SPEC = {1: ("replicas", ("int32",)),
                   2: ("selector", ("msg", "LabelSelector")),
                   3: ("template", ("msg", "PodTemplateSpec")),
                   4: ("minReadySeconds", ("int32",))}

REPLICASET_CONDITION = {1: ("type", ("str",)), 2: ("status", ("str",)),
                        3: ("lastTransitionTime", ("msg", "Time")),
                        4: ("reason", ("str",)), 5: ("message", ("str",))}

REPLICASET_STATUS = {1: ("replicas", ("int32",)),
                     2: ("fullyLabeledReplicas", ("int32",)),
                     3: ("observedGeneration", ("int64",)),
                     4: ("readyReplicas", ("int32",)),
                     5: ("availableReplicas", ("int32",)),
                     6: ("conditions", ("rep", ("msg", "ReplicaSetCondition"))),
                     7: ("terminatingReplicas", ("int32",))}

REPLICASET = {1: ("metadata", ("msg", "ObjectMeta")),
              2: ("spec", ("msg", "ReplicaSetSpec")),
              3: ("status", ("msg", "ReplicaSetStatus"))}

STATEFULSET_SPEC = {1: ("replicas", ("int32",)),
                    2: ("selector", ("msg", "LabelSelector")),
                    3: ("template", ("msg", "PodTemplateSpec")),
                    4: ("volumeClaimTemplates", ("rep", ("msg", None))),
                    5: ("serviceName", ("str",)),
                    6: ("podManagementPolicy", ("str",)),
                    7: ("updateStrategy", ("msg", None)),
                    8: ("revisionHistoryLimit", ("int32",)),
                    9: ("minReadySeconds", ("int32",)),
                    10: ("persistentVolumeClaimRetentionPolicy", ("msg", None)),
                    11: ("ordinals", ("msg", None))}

STATEFULSET_CONDITION = {1: ("type", ("str",)), 2: ("status", ("str",)),
                         3: ("lastTransitionTime", ("msg", "Time")),
                         4: ("reason", ("str",)), 5: ("message", ("str",))}

STATEFULSET_STATUS = {1: ("observedGeneration", ("int64",)),
                      2: ("replicas", ("int32",)),
                      3: ("readyReplicas", ("int32",)),
                      4: ("currentReplicas", ("int32",)),
                      5: ("updatedReplicas", ("int32",)),
                      6: ("currentRevision", ("str",)),
                      7: ("updateRevision", ("str",)),
                      9: ("collisionCount", ("int32",)),
                      10: ("conditions", ("rep", ("msg", "StatefulSetCondition"))),
                      11: ("availableReplicas", ("int32",))}

STATEFULSET = {1: ("metadata", ("msg", "ObjectMeta")),
               2: ("spec", ("msg", "StatefulSetSpec")),
               3: ("status", ("msg", "StatefulSetStatus"))}

DAEMONSET_SPEC = {1: ("selector", ("msg", "LabelSelector")),
                  2: ("template", ("msg", "PodTemplateSpec")),
                  3: ("updateStrategy", ("msg", None)),
                  4: ("minReadySeconds", ("int32",)),
                  6: ("revisionHistoryLimit", ("int32",))}

DAEMONSET_CONDITION = {1: ("type", ("str",)), 2: ("status", ("str",)),
                       3: ("lastTransitionTime", ("msg", "Time")),
                       4: ("reason", ("str",)), 5: ("message", ("str",))}

DAEMONSET_STATUS = {1: ("currentNumberScheduled", ("int32",)),
                    2: ("numberMisscheduled", ("int32",)),
                    3: ("desiredNumberScheduled", ("int32",)),
                    4: ("numberReady", ("int32",)),
                    5: ("observedGeneration", ("int64",)),
                    6: ("updatedNumberScheduled", ("int32",)),
                    7: ("numberAvailable", ("int32",)),
                    8: ("numberUnavailable", ("int32",)),
                    9: ("collisionCount", ("int32",)),
                    10: ("conditions", ("rep", ("msg", "DaemonSetCondition")))}

DAEMONSET = {1: ("metadata", ("msg", "ObjectMeta")),
             2: ("spec", ("msg", "DaemonSetSpec")),
             3: ("status", ("msg", "DaemonSetStatus"))}

# ----------------------------------------------------------------- batch ----

JOB_CONDITION = {1: ("type", ("str",)), 2: ("status", ("str",)),
                 3: ("lastProbeTime", ("msg", "Time")),
                 4: ("lastTransitionTime", ("msg", "Time")),
                 5: ("reason", ("str",)), 6: ("message", ("str",))}

UNCOUNTED_TERMINATED_PODS = {1: ("succeeded", ("rep", ("str",))),
                             2: ("failed", ("rep", ("str",)))}

JOB_SPEC = {1: ("parallelism", ("int32",)),
            2: ("completions", ("int32",)),
            3: ("activeDeadlineSeconds", ("int64",)),
            4: ("selector", ("msg", "LabelSelector")),
            5: ("manualSelector", ("bool",)),
            6: ("template", ("msg", "PodTemplateSpec")),
            7: ("backoffLimit", ("int32",)),
            8: ("ttlSecondsAfterFinished", ("int32",)),
            9: ("completionMode", ("str",)),
            10: ("suspend", ("bool",)),
            11: ("podFailurePolicy", ("msg", None)),
            12: ("backoffLimitPerIndex", ("int32",)),
            13: ("maxFailedIndexes", ("int32",)),
            14: ("podReplacementPolicy", ("str",)),
            15: ("managedBy", ("str",)),
            16: ("successPolicy", ("msg", None)),
            17: ("scheduling", ("msg", None))}

JOB_STATUS = {1: ("conditions", ("rep", ("msg", "JobCondition"))),
              2: ("startTime", ("msg", "Time")),
              3: ("completionTime", ("msg", "Time")),
              4: ("active", ("int32",)),
              5: ("succeeded", ("int32",)),
              6: ("failed", ("int32",)),
              7: ("completedIndexes", ("str",)),
              8: ("uncountedTerminatedPods", ("msg", "UncountedTerminatedPods")),
              9: ("ready", ("int32",)),
              10: ("failedIndexes", ("str",)),
              11: ("terminating", ("int32",))}

JOB = {1: ("metadata", ("msg", "ObjectMeta")),
       2: ("spec", ("msg", "JobSpec")),
       3: ("status", ("msg", "JobStatus"))}

JOB_TEMPLATE_SPEC = {1: ("metadata", ("msg", "ObjectMeta")),
                     2: ("spec", ("msg", "JobSpec"))}

CRON_JOB_SPEC = {1: ("schedule", ("str",)),
                 2: ("startingDeadlineSeconds", ("int64",)),
                 3: ("concurrencyPolicy", ("str",)),
                 4: ("suspend", ("bool",)),
                 5: ("jobTemplate", ("msg", "JobTemplateSpec")),
                 6: ("successfulJobsHistoryLimit", ("int32",)),
                 7: ("failedJobsHistoryLimit", ("int32",)),
                 8: ("timeZone", ("str",))}

CRON_JOB_STATUS = {1: ("active", ("rep", ("msg", "ObjectReference"))),
                   4: ("lastScheduleTime", ("msg", "Time")),
                   5: ("lastSuccessfulTime", ("msg", "Time"))}

CRONJOB = {1: ("metadata", ("msg", "ObjectMeta")),
           2: ("spec", ("msg", "CronJobSpec")),
           3: ("status", ("msg", "CronJobStatus"))}

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

NETWORK_POLICY_SPEC = {1: ("podSelector", ("msg", "LabelSelector")),
                       2: ("ingress", ("rep", ("msg", None))),
                       3: ("egress", ("rep", ("msg", None))),
                       4: ("policyTypes", ("rep", ("str",)))}

NETWORK_POLICY = {1: ("metadata", ("msg", "ObjectMeta")),
                  2: ("spec", ("msg", "NetworkPolicySpec"))}

INGRESS_CLASS_SPEC = {1: ("controller", ("str",)),
                      2: ("parameters", ("msg", None))}

INGRESS_CLASS = {1: ("metadata", ("msg", "ObjectMeta")),
                 2: ("spec", ("msg", "IngressClassSpec"))}

RESOURCE_QUOTA_SPEC = {1: ("hard", ("map", ("str",))),
                       2: ("scopes", ("rep", ("str",))),
                       3: ("scopeSelector", ("msg", None))}

RESOURCE_QUOTA_STATUS = {1: ("hard", ("map", ("str",))),
                         2: ("used", ("map", ("str",)))}

RESOURCE_QUOTA = {1: ("metadata", ("msg", "ObjectMeta")),
                  2: ("spec", ("msg", "ResourceQuotaSpec")),
                  3: ("status", ("msg", "ResourceQuotaStatus"))}

LIMIT_RANGE = {1: ("metadata", ("msg", "ObjectMeta")),
               2: ("spec", ("msg", "LimitRangeSpec"))}

LIMIT_RANGE_SPEC = {1: ("limits", ("rep", ("msg", "LimitRangeItem")))}

LIMIT_RANGE_ITEM = {1: ("type", ("str",)),
                    2: ("max", ("map", ("str",))),
                    3: ("min", ("map", ("str",))),
                    4: ("default", ("map", ("str",))),
                    5: ("defaultRequest", ("map", ("str",))),
                    6: ("maxLimitRequestRatio", ("map", ("str",)))}

IP_ADDRESS_SPEC = {1: ("parentRef", ("msg", None))}

IP_ADDRESS = {1: ("metadata", ("msg", "ObjectMeta")),
              2: ("spec", ("msg", "IPAddressSpec"))}

CSI_NODE_SPEC = {1: ("drivers", ("rep", ("msg", None)))}

CSI_NODE = {1: ("metadata", ("msg", "ObjectMeta")),
            2: ("spec", ("msg", "CSINodeSpec"))}

SERVICE_CIDR_SPEC = {1: ("cidrs", ("rep", ("str",)))}

SERVICE_CIDR_STATUS = {1: ("conditions", ("rep", ("msg", None)))}

SERVICE_CIDR = {1: ("metadata", ("msg", "ObjectMeta")),
                2: ("spec", ("msg", "ServiceCIDRSpec")),
                3: ("status", ("msg", "ServiceCIDRStatus"))}

FLOW_SCHEMA_SPEC = {1: ("priorityLevelConfiguration", ("msg", None)),
                    2: ("matchingPrecedence", ("int32",)),
                    3: ("distinguisherMethod", ("msg", None)),
                    4: ("rules", ("rep", ("msg", None)))}

FLOW_SCHEMA_STATUS = {1: ("conditions", ("rep", ("msg", None)))}

FLOW_SCHEMA = {1: ("metadata", ("msg", "ObjectMeta")),
               2: ("spec", ("msg", "FlowSchemaSpec")),
               3: ("status", ("msg", "FlowSchemaStatus"))}

PRIORITY_LEVEL_SPEC = {1: ("type", ("str",)),
                       2: ("limited", ("msg", None)),
                       3: ("exempt", ("msg", None))}

PRIORITY_LEVEL_STATUS = {1: ("conditions", ("rep", ("msg", None)))}

PRIORITY_LEVEL = {1: ("metadata", ("msg", "ObjectMeta")),
                  2: ("spec", ("msg", "PriorityLevelSpec")),
                  3: ("status", ("msg", "PriorityLevelStatus"))}

VALIDATING_POLICY_SPEC = {1: ("paramKind", ("msg", None)),
                          2: ("matchConstraints", ("msg", None)),
                          3: ("validations", ("rep", ("msg", None))),
                          4: ("failurePolicy", ("str",)),
                          5: ("auditAnnotations", ("rep", ("msg", None))),
                          6: ("matchConditions", ("rep", ("msg", None))),
                          7: ("variables", ("rep", ("msg", None)))}

VALIDATING_POLICY_STATUS = {1: ("observedGeneration", ("int64",)),
                            2: ("typeChecking", ("msg", None)),
                            3: ("conditions", ("rep", ("msg", None)))}

VALIDATING_POLICY = {1: ("metadata", ("msg", "ObjectMeta")),
                     2: ("spec", ("msg", "ValidatingPolicySpec")),
                     3: ("status", ("msg", "ValidatingPolicyStatus"))}

VALIDATING_POLICY_BINDING_SPEC = {1: ("policyName", ("str",)),
                                  2: ("paramRef", ("msg", None)),
                                  3: ("matchResources", ("msg", None)),
                                  4: ("validationActions", ("rep", ("str",)))}

VALIDATING_POLICY_BINDING = {1: ("metadata", ("msg", "ObjectMeta")),
                             2: ("spec", ("msg", "ValidatingPolicyBindingSpec"))}

# ------------------------------------------------------------- policy ----

PDB_SPEC = {1: ("minAvailable", ("msg", "IntOrString")),
            2: ("selector", ("msg", "LabelSelector")),
            3: ("maxUnavailable", ("msg", "IntOrString")),
            4: ("unhealthyPodEvictionPolicy", ("str",))}

PDB_STATUS = {1: ("observedGeneration", ("int64",)),
              2: ("disruptedPods", ("map", ("msg", "Time"))),
              3: ("disruptionsAllowed", ("int32",)),
              4: ("currentHealthy", ("int32",)),
              5: ("desiredHealthy", ("int32",)),
              6: ("expectedPods", ("int32",)),
              7: ("conditions", ("rep", ("msg", None)))}

PDB = {1: ("metadata", ("msg", "ObjectMeta")),
       2: ("spec", ("msg", "PDBSpec")),
       3: ("status", ("msg", "PDBStatus"))}

INT_OR_STRING = {1: ("type", ("int64",)), 2: ("intVal", ("int32",)),
                 3: ("strVal", ("str",))}

# ---------------------------------------------------------- storage ----

CSI_DRIVER_SPEC = {1: ("attachRequired", ("bool",)),
                   2: ("podInfoOnMount", ("bool",)),
                   3: ("volumeLifecycleModes", ("rep", ("str",))),
                   4: ("storageCapacity", ("bool",)),
                   5: ("fsGroupPolicy", ("str",)),
                   6: ("tokenRequests", ("rep", ("msg", None))),
                   7: ("requiresRepublish", ("bool",)),
                   8: ("seLinuxMount", ("bool",)),
                   9: ("nodeAllocatableUpdatePeriodSeconds", ("int64",)),
                   10: ("serviceAccountTokenInSecrets", ("bool",)),
                   11: ("preventPodSchedulingIfMissing", ("bool",))}

CSI_DRIVER = {1: ("metadata", ("msg", "ObjectMeta")),
              2: ("spec", ("msg", "CSIDriverSpec"))}

# ------------------------------------------------- admissionregistration ----

WEBHOOK_CONFIG_SPEC = {2: ("webhooks", ("rep", ("msg", None)))}

MUTATING_WEBHOOK_CONFIG = {1: ("metadata", ("msg", "ObjectMeta")),
                           2: ("webhooks", ("rep", ("msg", None)))}

VALIDATING_WEBHOOK_CONFIG = {1: ("metadata", ("msg", "ObjectMeta")),
                             2: ("webhooks", ("rep", ("msg", None)))}

# ------------------------------------------------------------ scheduling ---

PRIORITY_CLASS = {1: ("metadata", ("msg", "ObjectMeta")),
                  2: ("value", ("int32",)),
                  3: ("globalDefault", ("bool",)),
                  4: ("description", ("str",)),
                  5: ("preemptionPolicy", ("str",))}

# ---------------------------------------------------------- openshift ---

ROUTE_SPEC = {1: ("host", ("str",)),
              2: ("path", ("str",)),
              3: ("to", ("msg", None)),
              4: ("alternateBackends", ("rep", ("msg", None))),
              5: ("port", ("msg", None)),
              6: ("tls", ("msg", None)),
              7: ("wildcardPolicy", ("str",)),
              8: ("subdomain", ("str",)),
              9: ("httpHeaders", ("msg", None))}

ROUTE_INGRESS = {1: ("host", ("str",)), 2: ("routerName", ("str",)),
                 3: ("conditions", ("rep", ("msg", None))),
                 4: ("wildcardPolicy", ("str",)),
                 5: ("routerCanonicalHostname", ("str",))}

ROUTE_STATUS = {1: ("ingress", ("rep", ("msg", "RouteIngress")))}

ROUTE = {1: ("metadata", ("msg", "ObjectMeta")),
         2: ("spec", ("msg", "RouteSpec")),
         3: ("status", ("msg", "RouteStatus"))}

IMAGE_STREAM_SPEC = {1: ("dockerImageRepository", ("str",)),
                     2: ("tags", ("rep", ("msg", None))),
                     3: ("lookupPolicy", ("msg", None))}

IMAGE_STREAM_STATUS = {1: ("dockerImageRepository", ("str",)),
                       2: ("tags", ("rep", ("msg", None))),
                       3: ("publicDockerImageRepository", ("str",))}

IMAGE_STREAM = {1: ("metadata", ("msg", "ObjectMeta")),
                2: ("spec", ("msg", "ImageStreamSpec")),
                3: ("status", ("msg", "ImageStreamStatus"))}

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
    "Time": TIME,
    "ObjectMeta": META,
    "OwnerReference": OWNER_REF,
    "FieldsV1": FIELDS_V1,
    "ManagedFieldsEntry": MANAGED_FIELDS,
    "ObjectReference": OBJ_REF,
    "LocalObjectReference": LOCAL_OBJ_REF,
    "LabelSelector": LABEL_SELECTOR,
    "LabelSelectorRequirement": LABEL_SEL_REQ,
    "ServicePort": SERVICE_PORT,
    "ServiceSpec": SERVICE_SPEC,
    "PodSpec": POD_SPEC,
    "PodTemplateSpec": POD_TEMPLATE_SPEC,
    "PodCondition": POD_CONDITION,
    "PodStatus": POD_STATUS,
    "Container": CONTAINER,
    "ContainerStatus": CONTAINER_STATUS,
    "ContainerState": CONTAINER_STATE,
    "NodeSpec": NODE_SPEC,
    "NodeStatus": NODE_STATUS,
    "NodeCondition": NODE_CONDITION,
    "NodeAddress": NODE_ADDRESS,
    "Taint": TAINT,
    "PVSpec": PV_SPEC,
    "PVStatus": PV_STATUS,
    "PVCSpec": PVC_SPEC,
    "PVCStatus": PVC_STATUS,
    "DeploymentSpec": DEPLOYMENT_SPEC,
    "DeploymentStatus": DEPLOYMENT_STATUS,
    "DeploymentCondition": DEPLOYMENT_CONDITION,
    "ReplicaSetSpec": REPLICASET_SPEC,
    "ReplicaSetStatus": REPLICASET_STATUS,
    "ReplicaSetCondition": REPLICASET_CONDITION,
    "StatefulSetSpec": STATEFULSET_SPEC,
    "StatefulSetStatus": STATEFULSET_STATUS,
    "StatefulSetCondition": STATEFULSET_CONDITION,
    "DaemonSetSpec": DAEMONSET_SPEC,
    "DaemonSetStatus": DAEMONSET_STATUS,
    "DaemonSetCondition": DAEMONSET_CONDITION,
    "JobSpec": JOB_SPEC,
    "JobStatus": JOB_STATUS,
    "JobCondition": JOB_CONDITION,
    "UncountedTerminatedPods": UNCOUNTED_TERMINATED_PODS,
    "JobTemplateSpec": JOB_TEMPLATE_SPEC,
    "CronJobSpec": CRON_JOB_SPEC,
    "CronJobStatus": CRON_JOB_STATUS,
    "PDBSpec": PDB_SPEC,
    "PDBStatus": PDB_STATUS,
    "IntOrString": INT_OR_STRING,
    "CSIDriverSpec": CSI_DRIVER_SPEC,
    "CSINodeSpec": CSI_NODE_SPEC,
    "IPAddressSpec": IP_ADDRESS_SPEC,
    "LimitRangeItem": LIMIT_RANGE_ITEM,
    "LimitRangeSpec": LIMIT_RANGE_SPEC,
    "ServiceCIDRSpec": SERVICE_CIDR_SPEC,
    "ServiceCIDRStatus": SERVICE_CIDR_STATUS,
    "ImageStreamSpec": IMAGE_STREAM_SPEC,
    "ImageStreamStatus": IMAGE_STREAM_STATUS,
    "FlowSchemaSpec": FLOW_SCHEMA_SPEC,
    "FlowSchemaStatus": FLOW_SCHEMA_STATUS,
    "PriorityLevelSpec": PRIORITY_LEVEL_SPEC,
    "PriorityLevelStatus": PRIORITY_LEVEL_STATUS,
    "ValidatingPolicySpec": VALIDATING_POLICY_SPEC,
    "ValidatingPolicyStatus": VALIDATING_POLICY_STATUS,
    "ValidatingPolicyBindingSpec": VALIDATING_POLICY_BINDING_SPEC,
    "NamespaceSpec": NAMESPACE_SPEC,
    "NamespaceStatus": NAMESPACE_STATUS,
    "ServiceStatus": SERVICE_STATUS,
    "NetworkPolicySpec": NETWORK_POLICY_SPEC,
    "IngressClassSpec": INGRESS_CLASS_SPEC,
    "ResourceQuotaSpec": RESOURCE_QUOTA_SPEC,
    "ResourceQuotaStatus": RESOURCE_QUOTA_STATUS,
    "RouteSpec": ROUTE_SPEC,
    "RouteStatus": ROUTE_STATUS,
    "RouteIngress": ROUTE_INGRESS,
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
    "ResourceQuota": RESOURCE_QUOTA,
    "LimitRange": LIMIT_RANGE,
    "PriorityClass": PRIORITY_CLASS,
    "PodDisruptionBudget": PDB,
    "CSIDriver": CSI_DRIVER,
    "MutatingWebhookConfiguration": MUTATING_WEBHOOK_CONFIG,
    "ValidatingWebhookConfiguration": VALIDATING_WEBHOOK_CONFIG,
    "Route": ROUTE,
    "ImageStream": IMAGE_STREAM,
    "IPAddress": IP_ADDRESS,
    "CSINode": CSI_NODE,
    "ServiceCIDR": SERVICE_CIDR,
    "LimitRange": LIMIT_RANGE,
    "FlowSchema": FLOW_SCHEMA,
    "PriorityLevelConfiguration": PRIORITY_LEVEL,
    "ValidatingAdmissionPolicy": VALIDATING_POLICY,
    "ValidatingAdmissionPolicyBinding": VALIDATING_POLICY_BINDING,
    "APIService": APISERVICE,
    "CustomResourceDefinition": CUSTOM_RESOURCE_DEFINITION,
    "ControllerRevision": CONTROLLER_REVISION,
    "Endpoints": ENDPOINTS,
    "EndpointSlice": ENDPOINT_SLICE,
    # OpenShift native kinds (canonical openshift/api field numbers)
    "Image": {1: ("metadata", ("msg", "ObjectMeta")),
              2: ("dockerImageReference", ("str",)),
              3: ("dockerImageMetadata", ("msg", None)),
              4: ("dockerImageMetadataVersion", ("str",)),
              5: ("dockerImageManifest", ("str",)),
              6: ("dockerImageLayers", ("rep", ("msg", None))),
              7: ("signatures", ("rep", ("msg", None))),
              8: ("dockerImageSignatures", ("rep", ("bytes",))),
              9: ("dockerImageManifestMediaType", ("str",)),
              10: ("dockerImageConfig", ("str",))},
    "OAuthClient": {1: ("metadata", ("msg", "ObjectMeta")),
                    2: ("secret", ("str",)),
                    3: ("additionalSecrets", ("rep", ("str",))),
                    4: ("respondWithChallenges", ("bool",)),
                    5: ("redirectURIs", ("rep", ("str",))),
                    6: ("grantMethod", ("str",)),
                    7: ("scopeRestrictions", ("rep", ("msg", None))),
                    8: ("accessTokenMaxAgeSeconds", ("int32",)),
                    9: ("accessTokenInactivityTimeoutSeconds", ("int32",))},
    "OAuthAccessToken": {1: ("metadata", ("msg", "ObjectMeta")),
                         2: ("clientName", ("str",)),
                         3: ("expiresIn", ("int64",)),
                         4: ("scopes", ("rep", ("str",))),
                         5: ("redirectURI", ("str",)),
                         6: ("userName", ("str",)),
                         7: ("userUID", ("str",)),
                         8: ("authorizeToken", ("str",)),
                         9: ("refreshToken", ("str",)),
                         10: ("inactivityTimeoutSeconds", ("int32",))},
    "CSIStorageCapacity": {1: ("metadata", ("msg", "ObjectMeta")),
                           2: ("nodeTopology", ("msg", "LabelSelector")),
                           3: ("storageClassName", ("str",)),
                           4: ("capacity", ("msg", None)),
                           5: ("maximumVolumeSize", ("msg", None))},
}

# OpenShift native types use the same metadata/spec/status shape; field
# numbers for their spec/status are handled generically.
for _kind in ("OAuthAuthorizeToken",
              "OAuthClientAuthorization", "ImageStreamTag",
              "ImageStreamImage", "Config", "FeatureGate", "ClusterOperator",
              "Machine", "MachineSet", "MachineConfig", "Infrastructure"):
    SCHEMAS.setdefault(_kind, GENERIC)


def for_kind(kind: str, api_version: str = "") -> dict | None:
    """Resolve a schema for ``kind``, falling back to the generic
    metadata/spec/status shape so the object metadata still decodes."""
    return SCHEMAS.get(kind, GENERIC)
