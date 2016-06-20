from oslo_config import cfg

from microservices import utils


CONF = cfg.CONF

FILES_VOLUME = "files-volume"
GLOBAL_VOLUME = "global-volume"
ROLE_VOLUME = "role-volume"
SCRIPT_VOLUME = "script-volume"
START_CMD = ["python", "/opt/mcp_start_script/bin/start_script.py"]


def _get_image_name(service):
    return "%s/%s/%s:%s" % (CONF.builder.registry, CONF.images.namespace,
                            service["name"], CONF.images.tag)


def serialize_configmap(name, data):
    return {
        "apiVersion": "v1",
        "kind": "ConfigMap",
        "metadata": {
            "name": name,
            "mcp": "true"
        },
        "data": data
    }


def serialize_container_spec(service, name, cmd, globals_name, restart_policy):
    container = {
        "name": name,
        "image": _get_image_name(service),
        "command": START_CMD,
        "volumeMounts": [
            {
                "name": GLOBAL_VOLUME,
                "mountPath": "/etc/mcp/globals"
            },
            {
                "name": ROLE_VOLUME,
                "mountPath": "/etc/mcp/role"
            },
            {
                "name": SCRIPT_VOLUME,
                "mountPath": "/opt/mcp_start_script/bin"
            }
        ]
    }
    if "files" in cmd:
        container["volumeMounts"].append({
            "name": FILES_VOLUME,
            "mountPath": "/etc/mcp/files"
        })
    if service.get("probes", {}).get("readiness"):
        container["readinessProbe"] = {
            "exec": {
                "command": [service["probes"]["readiness"]]
            },
            "timeoutSeconds": 1
        }
    if service.get("probes", {}).get("liveness"):
        container["livenessProbe"] = {
            "exec": {
                "command": [service["probes"]["liveness"]]
            },
            "timeoutSeconds": 1
        }
    if service.get("container", {}).get("privileged"):
        container["securityContext"] = {"privileged": True}
    return {
        "metadata": {
            "name": name
        },
        "spec": {
            "containers": [container],
            "volumes": serialize_volumes(service, cmd, globals_name),
            "restartPolicy": restart_policy,
            "hostNetwork": service.get("container", {}).get("host-net", False)
        }
    }


def serialize_volumes(service, cmd, globals_name):
    vol = [
        {
            "name": GLOBAL_VOLUME,
            "configMap": {
                "name": globals_name,
                "items": [{"key": "configs",
                           "path": "globals.yaml"}]
            }
        },
        {
            "name": ROLE_VOLUME,
            "configMap": {
                "name": "%s-workflow" % cmd["name"],
                "items": [{"key": "workflow", "path": "role.yaml"}]
            }
        },
        {
            "name": SCRIPT_VOLUME,
            "configMap": {
                "name": globals_name,
                "items": [{"key": "start-script",
                           "path": "start_script.py"}]
            }
        }
    ]
    if "files" in cmd:
        vol.append({
            "name": FILES_VOLUME,
            "configMap": {
                "name": cmd["name"],
                "items": [{"key": k, "path": k} for k in cmd["files"]]
            }
        })
    return vol


def serialize_job(name, spec):
    return {
        "apiVersion": "batch/v1",
        "kind": "Job",
        "metadata": {
            "name": name,
            "mcp": "true"
        },
        "spec": {
            "template": spec
        }
    }


def serialize_deployment(name, spec):
    return {
        "apiVersion": "extensions/v1beta1",
        "kind": "Deployment",
        "metadata": {
            "name": name
        },
        "spec": {
            "replicas": 1,
            "template": {
                "metadata": {
                    "labels": {
                        "mcp": "true",
                        "app": name
                    }
                },
                "spec": spec["spec"]
            }
        }
    }


def serialize_service(name, ports):
    ports_spec = [{"protocol": "TCP", "port": p["port"],
                   "targetPort": p["port"], "name": utils.k8s_name(p["name"])}
                  for p in ports]
    return {
        "apiVersion": "v1",
        "kind": "Service",
        "metadata": {
            "name": name,
            "mcp": "true"
        },
        "spec": {
            "type": "NodePort",
            "selector": {
                "app": name
            },
            "ports": ports_spec
        }
    }
