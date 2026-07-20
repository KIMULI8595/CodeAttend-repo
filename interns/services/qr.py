import qrcode

from io import BytesIO


class QRService:

    @staticmethod
    def generate_qr(intern):

        qr_data = str(intern.qr_code)

        qr = qrcode.make(qr_data)

        buffer = BytesIO()

        qr.save(
            buffer,
            format="PNG"
        )

        return buffer.getvalue()