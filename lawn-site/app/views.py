import base64
from .serializers import YourModelSerializer
from rest_framework.response import Response
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.parsers import MultiPartParser, FormParser
import os
import cv2
import numpy as np
import tensorflow as tf


def preprocess_image(image_path, desired_size=(300, 300)):
    if not os.path.exists(image_path):
        print(f"File not found: {image_path}")
        return None
    image = cv2.imread(image_path)
    if image is None:
        print(f"Failed to load image: {image_path}")
        return None
    # image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)  # Convert to RGB
    image = cv2.resize(image, desired_size)
    image = image / 255.0  # Normalize
    return image


def postprocess_and_fill_lawn(image, mask):
    _, binary_mask = cv2.threshold(mask, 0.5, 1, cv2.THRESH_BINARY)
    lawn_mask = np.zeros_like(image)
    contours, _ = cv2.findContours(
        np.uint8(binary_mask), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    fill_color = (255, 255, 255)
    for contour in contours:
        cv2.fillPoly(lawn_mask, [contour], fill_color)
    return lawn_mask


def adjust_brightness_contrast(image, alpha=1.0, beta=0):
    adjusted_image = cv2.convertScaleAbs(image, alpha=alpha, beta=beta)
    return adjusted_image


def overlay_images_with_mask(background, overlay, lawn_mask, alpha=0.7):
    background = background.astype(np.uint8)
    overlay = overlay.astype(np.uint8)
    overlay_blend = cv2.addWeighted(background, 1 - alpha, overlay, alpha, 0)
    return np.where(lawn_mask == 1, overlay_blend, background)


class IndexView(APIView):
    parser_classes = (MultiPartParser, FormParser)

    def post(self, request, *args, **kwargs):
        model = tf.keras.models.load_model('app/model.h5')
        model_serializer = YourModelSerializer(data=request.data)
        if model_serializer.is_valid():
            model_serializer.save()
            new_image_path = os.getcwd() + "/proj" + \
                str(model_serializer.data['image'])
            print(new_image_path)
            overlay_image_path = os.getcwd() + "/proj/" + 'turf.jpg'
            new_image = preprocess_image(new_image_path)
            if new_image is not None:
                # Apply brightness and contrast adjustment
                new_image_adjusted = adjust_brightness_contrast(
                    new_image * 255, alpha=0.8, beta=30)  # Modify alpha and beta as needed

                predicted_mask = model.predict(
                    np.array([new_image_adjusted]))[0]
                lawn_mask = postprocess_and_fill_lawn(
                    new_image_adjusted, predicted_mask[:, :, 0])
                lawn_mask = (lawn_mask > 0).astype(np.uint8)

                overlay_image = cv2.imread(overlay_image_path)
                overlay_image = cv2.resize(
                    overlay_image, (lawn_mask.shape[1], lawn_mask.shape[0]))
                final_image = overlay_images_with_mask(
                    new_image_adjusted, overlay_image, lawn_mask)

                final_image_rgb = cv2.cvtColor(final_image, cv2.COLOR_BGR2RGB)
                # Convert final image to base64 for transmission
                _, buffer = cv2.imencode('.jpg', final_image)
                image_base64 = base64.b64encode(buffer).decode()
                return Response(image_base64, status=status.HTTP_200_OK)
        else:
            print('error', model_serializer.errors)
            return Response(model_serializer.errors, status=status.HTTP_400_BAD_REQUEST)
