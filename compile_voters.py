import solcx

SOLC_VERSION = '0.8.18'

print(solcx.get_installed_solc_versions())
if SOLC_VERSION not in [str(v) for v in solcx.get_installed_solc_versions()]:
    solcx.install_solc(SOLC_VERSION)

with open('voters.sol', 'r') as file:
    source_code = file.read()

compiled = solcx.compile_source(
    source_code,
    output_values=['abi', 'bin'],
    solc_version=SOLC_VERSION
)

contract_id, contract_interface = compiled.popitem()

abi = contract_interface['abi']
bytecode = contract_interface['bin']

print(abi)
print(bytecode)