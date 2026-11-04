# Vault policy and Kubernetes auth role (apply via vault CLI / Terraform).
# vault policy write dograh - <<EOF
# path "secret/data/dograh/*" { capabilities = ["read"] }
# EOF
#
# vault write auth/kubernetes/role/dograh \
#   bound_service_account_names=dograh \
#   bound_service_account_namespaces=dograh \
#   policies=dograh \
#   ttl=1h
