# tools/make_dev_cert.py
from datetime import datetime, timedelta, UTC
import ipaddress
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID

# 1) Generate key
key = rsa.generate_private_key(public_exponent=65537, key_size=2048)

# 2) Build cert (CN=localhost, with SANs for localhost & 127.0.0.1)
subject = issuer = x509.Name([
    x509.NameAttribute(NameOID.COMMON_NAME, u"localhost"),
])
san = x509.SubjectAlternativeName([
    x509.DNSName(u"localhost"),
    x509.IPAddress(ipaddress.IPv4Address("127.0.0.1")),
])

cert = (
    x509.CertificateBuilder()
    .subject_name(subject)
    .issuer_name(issuer)
    .public_key(key.public_key())
    .serial_number(x509.random_serial_number())
    .not_valid_before(datetime.now(UTC) - timedelta(days=1))
    .not_valid_after(datetime.now(UTC) + timedelta(days=365*3))   # valid ~3 years
    .add_extension(san, critical=False)
    .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
    .sign(private_key=key, algorithm=hashes.SHA256())
)

# 3) Write files
with open("localhost.pem", "wb") as f:
    f.write(cert.public_bytes(serialization.Encoding.PEM))

with open("localhost-key.pem", "wb") as f:
    f.write(
        key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        )
    )

print("Wrote localhost.pem and localhost-key.pem")
