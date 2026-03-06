"""
One-time script to convert TensorFlow/Keras models to ONNX format.
Run this in an environment with TensorFlow installed.
"""

import os
import tensorflow as tf
import tf2onnx
import json

def convert_keras_to_onnx(model_dir, output_name="model.onnx"):
    """
    Convert a Keras model (model.json + weights.h5) to ONNX format.
    
    Parameters
    ----------
    model_dir : str
        Directory containing model.json and weights.h5
    output_name : str
        Name of output ONNX file
    """
    
    # Load Keras model
    json_path = os.path.join(model_dir, "model.json")
    weights_path = os.path.join(model_dir, "weights.h5")
    
    with open(json_path, 'r') as f:
        model_json = f.read()
    
    model = tf.keras.models.model_from_json(model_json)
    model.load_weights(weights_path)
    
    # Get input shape from model
    input_shape = model.input_shape
    print(f"Model input shape: {input_shape}")
    
    # Convert to ONNX
    # For LSTM models, input is typically (batch, sequence_length, features)
    # Use None for dynamic dimensions
    spec = (tf.TensorSpec((None, None, input_shape[-1]), tf.float32, name="input"),)
    
    output_path = os.path.join(model_dir, output_name)
    model_proto, _ = tf2onnx.convert.from_keras(model, input_signature=spec, output_path=output_path)
    
    print(f"Converted: {output_path}")
    return output_path


def convert_all_augmenter_models(augmenter_base_dir):
    """
    Convert all augmenter models in the directory structure.
    
    Expected structure:
        augmenter_base_dir/
            LSTM/
                v0.3_lower/
                    model.json
                    weights.h5
                v0.3_upper/
                    model.json
                    weights.h5
    """
    
    model_dirs = []
    
    # Find all directories containing model.json
    for root, dirs, files in os.walk(augmenter_base_dir):
        if "model.json" in files and "weights.h5" in files:
            model_dirs.append(root)
    
    print(f"Found {len(model_dirs)} models to convert:")
    for d in model_dirs:
        print(f"  - {d}")
    
    # Convert each model
    for model_dir in model_dirs:
        print(f"\nConverting: {model_dir}")
        try:
            convert_keras_to_onnx(model_dir)
            print("  Success!")
        except Exception as e:
            print(f"  Failed: {e}")


if __name__ == "__main__":
    import argparse
    
    # parser = argparse.ArgumentParser(description="Convert Keras models to ONNX")
    # parser.add_argument("--augmenter_dir", type=str, required=True,
    #                     help="Path to MarkerAugmenter directory")
    
    # args = parser.parse_args()
    
    # convert_all_augmenter_models(args.augmenter_dir)
    augmenter_dir = r"D:\axon-ai\opencap-core\MarkerAugmenter"
    convert_all_augmenter_models(augmenter_dir)