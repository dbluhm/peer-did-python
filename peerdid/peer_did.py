import re
from typing import List, Optional

from peerdid.core.peer_did_helper import (
    create_multibase_encnumbasis,
    Numalgo2Prefix,
    encode_service,
    decode_multibase_encnumbasis,
    decode_service,
)
from peerdid.core.peer_did_validation import (
    validate_create_peer_did_numalgo_0_input,
    validate_create_peer_did_numalgo_2_input,
    validate_verification_material_auth,
    validate_verification_material_agreem,
)
from peerdid.did_doc import DIDDocPeerDID, VerificationMethodPeerDID
from peerdid.errors import MalformedPeerDIDError
from peerdid.types import (
    PEER_DID,
    PublicKeyAgreement,
    PublicKeyAuthentication,
    JSON,
    VerificationMaterialFormatPeerDID,
)


def is_peer_did(peer_did: PEER_DID) -> bool:
    """
    Checks if peer_did parameter matches Peer DID spec
    (https://identity.foundation/peer-did-method-spec/index.html#matching-regex)
    :param peer_did: peer_did to check
    :return: True if peer_did matches spec, otherwise False
    """
    if peer_did is None:
        return False
    peer_did_pattern = re.compile(
        r"^did:peer:(([0](z)([1-9a-km-zA-HJ-NP-Z]{46,47}))|(2((\.[AEVID](z)([1-9a-km-zA-HJ-NP-Z]{46,47}))+"
        r"(\.(S)[0-9a-zA-Z=]*)?)))$"
    )
    return bool(re.match(peer_did_pattern, peer_did))


def create_peer_did_numalgo_0(inception_key: PublicKeyAuthentication) -> PEER_DID:
    """
    Generates peer_did according to the zero algorithm
    (https://identity.foundation/peer-did-method-spec/index.html#generation-method).
    For this type of algorithm did_doc can be obtained from peer_did
    :param inception_key: the key that creates the DID and authenticates when exchanging it with the first peer
    :raises TypeError: if the inception_key is not instance of PublicKeyAuthentication
    :raises ValueError: if the inception_key is not correctly encoded
    :return: generated peer_did
    """
    validate_create_peer_did_numalgo_0_input(inception_key)
    return "did:peer:0" + create_multibase_encnumbasis(inception_key)


def create_peer_did_numalgo_2(
    encryption_keys: List[PublicKeyAgreement],
    signing_keys: List[PublicKeyAuthentication],
    service: Optional[JSON],
) -> PEER_DID:
    """
    Generates peer_did according to the second algorithm
    (https://identity.foundation/peer-did-method-spec/index.html#generation-method).
    For this type of algorithm did_doc can be obtained from peer_did
    :param encryption_keys: list of encryption keys
    :param signing_keys: list of signing keys
    :param service: JSON string conforming to the DID specification (https://www.w3.org/TR/did-core/#services)
        or None if there is no services expected for this DID
    :raises TypeError:
        1. if at least one of encryption keys is not instance of PublicKeyAgreement or
            at least one of signing keys is not instance of PublicKeyAuthentication
        2. if service is not JSON type
    :raises ValueError:
        1. if at least one of keys is not properly encoded
        2. if service is not valid JSON
    :return: generated peer_did
    """
    validate_create_peer_did_numalgo_2_input(encryption_keys, signing_keys, service)

    enc_sep = "." + Numalgo2Prefix.KEY_AGREEMENT.value
    auth_sep = "." + Numalgo2Prefix.AUTHENTICATION.value
    encryption_keys_str = (
        enc_sep
        + enc_sep.join(create_multibase_encnumbasis(key) for key in encryption_keys)
        if encryption_keys
        else ""
    )
    auth_keys_str = (
        auth_sep
        + auth_sep.join(create_multibase_encnumbasis(key) for key in signing_keys)
        if signing_keys
        else ""
    )
    service_str = encode_service(service) if service else ""

    peer_did = "did:peer:2" + encryption_keys_str + auth_keys_str + service_str
    return peer_did


def resolve_peer_did(
    peer_did: PEER_DID,
    format: VerificationMaterialFormatPeerDID = VerificationMaterialFormatPeerDID.MULTIBASE,
) -> JSON:
    """
    Resolves did_doc from peer_did
    :param peer_did: peer_did to resolve
    :param format: the format of public keys in the DID DOC. Default format is multibase.
    :raises MalformedPeerDIDError: if peer_did parameter does not match peer_did spec
    :return: resolved did_doc as a JSON string
    """
    if not is_peer_did(peer_did):
        raise MalformedPeerDIDError("Does not match peer DID regexp")
    if peer_did[9] == "0":
        did_doc = _build_did_doc_numalgo_0(peer_did=peer_did, format=format)
    else:
        did_doc = _build_did_doc_numalgo_2(peer_did=peer_did, format=format)
    return did_doc.to_json()


def _build_did_doc_numalgo_0(
    peer_did: PEER_DID, format: VerificationMaterialFormatPeerDID
) -> DIDDocPeerDID:
    verification_material = __do_decode_multibase_encnumbasis(peer_did[10:], format)
    validate_verification_material_auth(verification_material)
    return DIDDocPeerDID(
        did=peer_did,
        authentication=[
            VerificationMethodPeerDID(did=peer_did, ver_material=verification_material)
        ],
    )


def _build_did_doc_numalgo_2(
    peer_did: PEER_DID, format: VerificationMaterialFormatPeerDID
) -> DIDDocPeerDID:
    keys = peer_did[11:]
    keys = keys.split(".")
    service = ""
    authentication = []
    key_agreement = []

    for key in keys:
        prefix = key[0]
        if prefix == Numalgo2Prefix.SERVICE.value:
            service = key[1:]
        elif prefix == Numalgo2Prefix.AUTHENTICATION.value:
            verification_material = __do_decode_multibase_encnumbasis(key[1:], format)
            validate_verification_material_auth(verification_material)
            authentication.append(
                VerificationMethodPeerDID(
                    did=peer_did, ver_material=verification_material
                )
            )
        elif prefix == Numalgo2Prefix.KEY_AGREEMENT.value:
            verification_material = __do_decode_multibase_encnumbasis(key[1:], format)
            validate_verification_material_agreem(verification_material)
            key_agreement.append(
                VerificationMethodPeerDID(
                    did=peer_did, ver_material=verification_material
                )
            )
        else:
            raise MalformedPeerDIDError("Unknown prefix: {}.".format(prefix))
    decoded_service = __do_decode_service(service, peer_did)

    return DIDDocPeerDID(
        did=peer_did,
        authentication=authentication,
        key_agreement=key_agreement,
        service=decoded_service,
    )


def __do_decode_multibase_encnumbasis(
    multibase: str, ver_material_format: VerificationMaterialFormatPeerDID
):
    try:
        return decode_multibase_encnumbasis(multibase, ver_material_format)
    except (ValueError, TypeError) as e:
        raise MalformedPeerDIDError("Invalid key {}".format(multibase)) from e


def __do_decode_service(service: str, peer_did: PEER_DID):
    try:
        return decode_service(service, peer_did)
    except (ValueError, TypeError) as e:
        raise MalformedPeerDIDError("Invalid service") from e


# the method is not needed for the static layer, because did_doc can be obtained from peer_did and vice versa.
# But the method will be needed for dynamic layer support
# def save_did_doc(did_doc: JSON, storage: Optional[Storage]):
#     """
#     Saves did_doc to a storage
#     :param did_doc: did_doc to save
#     :param storage: repository responsible for did_doc saving
#     """
#     pass
