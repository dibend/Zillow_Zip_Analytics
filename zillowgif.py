# Required libraries: pandas, requests, matplotlib, imageio
# Install them using: pip install pandas requests matplotlib imageio

import pandas as pd
import requests
import matplotlib.pyplot as plt
import imageio
import os
import tempfile
from datetime import datetime

# URL of the Zillow ZHVI data (middle tier, SFR/Condo, smoothed, seasonally adjusted, by month)
DATA_URL = 'https://files.zillowstatic.com/research/public_csvs/zhvi/Zip_zhvi_uc_sfrcondo_tier_0.33_0.67_sm_sa_month.csv'
# Local filename to save the downloaded CSV
CSV_FILENAME = 'zhvi_zip_data.csv'

def download_data(url, filename):
    """
    Downloads data from the given URL and saves it locally.
    Retries are not implemented, but could be added for more robustness.
    """
    print(f"Downloading data from {url}...")
    try:
        # Make a GET request to the URL
        response = requests.get(url, stream=True)
        # Raise an exception for bad status codes (4xx or 5xx)
        response.raise_for_status()
        
        # Write the content to a local file
        with open(filename, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192): # Process in chunks
                f.write(chunk)
        print(f"Data downloaded successfully and saved as {filename}")
        return True
    except requests.exceptions.RequestException as e:
        print(f"Error downloading data: {e}")
        return False

def generate_zhvi_animation(zip_code_str):
    """
    Generates an animated GIF of the Zillow Home Value Index (ZHVI)
    for the specified ZIP code.
    """
    # Step 1: Ensure data is downloaded
    if not os.path.exists(CSV_FILENAME):
        if not download_data(DATA_URL, CSV_FILENAME):
            print("Failed to download data. Exiting.")
            return
    
    # Step 2: Load data into pandas DataFrame
    print(f"Loading ZHVI data from {CSV_FILENAME}...")
    try:
        df = pd.read_csv(CSV_FILENAME)
    except Exception as e:
        print(f"Error reading CSV file {CSV_FILENAME}: {e}")
        return

    # Step 3: Filter data for the specified ZIP code
    # Zillow uses 'RegionName' for ZIP codes, which are often stored as integers.
    try:
        zip_code_int = int(zip_code_str)
    except ValueError:
        print(f"Invalid ZIP code format: '{zip_code_str}'. Please enter a numeric ZIP code.")
        return

    # Filter the DataFrame for the given ZIP code
    zip_data_row = df[df['RegionName'] == zip_code_int]

    if zip_data_row.empty:
        print(f"ZIP code {zip_code_str} (numeric: {zip_code_int}) not found in the dataset.")
        print("Please ensure the ZIP code is correct and exists in the Zillow dataset.")
        return

    # Step 4: Identify and extract time series data (date columns and ZHVI values)
    date_columns = []
    for col_name in df.columns:
        try:
            # Zillow uses 'YYYY-MM-DD' format for its monthly data columns
            datetime.strptime(str(col_name), '%Y-%m-%d')
            date_columns.append(str(col_name))
        except (ValueError, TypeError):
            # This column name is not in the expected date format or not a string
            continue
    
    if not date_columns:
        print("Could not automatically identify date columns containing ZHVI values.")
        print("Please check the CSV file structure.")
        return

    # Extract the ZHVI values for the identified date columns for the specific ZIP code
    # .squeeze() converts single-row DataFrame to a Series
    zhvi_series = zip_data_row[date_columns].squeeze() 

    if zhvi_series.empty or zhvi_series.isnull().all():
        print(f"No ZHVI data available or all data is null for ZIP code {zip_code_str}.")
        return

    # Convert date string index to datetime objects for proper plotting
    time_index = pd.to_datetime(zhvi_series.index)
    values = zhvi_series.values

    # Step 5: Generate frames for the animation
    frames = []
    # Create a temporary directory to store individual frames
    with tempfile.TemporaryDirectory() as temp_dir:
        print(f"Generating frames for animation in temporary directory: {temp_dir}...")

        # Determine a step for frames if there are too many data points to keep GIF reasonable
        num_points = len(time_index)
        frame_step = 1
        max_frames_for_gif = 150 # Adjust for desired GIF length/smoothness
        if num_points > max_frames_for_gif:
            frame_step = max(1, num_points // max_frames_for_gif) 
            print(f"Dataset has {num_points} monthly points. Plotting every {frame_step}th point for the animation.")

        # Extract City and State for a more descriptive title
        city_name = zip_data_row['City'].iloc[0]
        state_abbr = zip_data_row['State'].iloc[0]
        location_info = f"{city_name}, {state_abbr}"

        # Overall min/max for consistent Y-axis scaling across frames
        overall_min_val = zhvi_series.min()
        overall_max_val = zhvi_series.max()
        y_padding = (overall_max_val - overall_min_val) * 0.05 # 5% padding
        if y_padding == 0: # Handle case where all values are the same
            y_padding = overall_min_val * 0.1 if overall_min_val != 0 else 10000


        for i in range(0, num_points, frame_step):
            current_time_subset = time_index[:i+1]
            current_values_subset = values[:i+1]

            fig, ax = plt.subplots(figsize=(12, 7)) # Create a new figure for each frame
            ax.plot(current_time_subset, current_values_subset, marker='.', linestyle='-', color='dodgerblue')
            
            # Set consistent plot limits based on the entire dataset for this ZIP
            ax.set_xlim(time_index.min(), time_index.max())
            ax.set_ylim(overall_min_val - y_padding, overall_max_val + y_padding)

            # Titles and labels
            current_month_year = time_index[i].strftime('%Y-%m')
            ax.set_title(f"Zillow Home Value Index (ZHVI) for ZIP: {zip_code_str} ({location_info})\nAs of {current_month_year}", fontsize=15)
            ax.set_xlabel("Year-Month", fontsize=12)
            ax.set_ylabel("Home Value Index (USD)", fontsize=12)
            
            # Formatting
            ax.grid(True, linestyle='--', alpha=0.7)
            plt.xticks(rotation=45, ha="right") # Rotate x-axis labels for better readability
            plt.tight_layout() # Adjust plot to prevent labels from being cut off

            frame_filename = os.path.join(temp_dir, f"frame_{i:04d}.png")
            plt.savefig(frame_filename)
            plt.close(fig) # Close the figure to free up memory
            
            frames.append(imageio.imread(frame_filename))
            if (i // frame_step) % 20 == 0 : # Print progress every 20 frames
                 print(f"  Generated frame {i // frame_step + 1}/{ (num_points-1)//frame_step + 1 }...")


        # Step 6: Create animated GIF from the frames
        gif_filename = f"zhvi_animation_{zip_code_str}.gif"
        print(f"Creating animated GIF: {gif_filename}...")
        
        num_actual_frames = len(frames)
        duration_per_frame_seconds = 0.15 # Default duration per frame in seconds
        if num_actual_frames < 50:
            duration_per_frame_seconds = 0.3
        elif num_actual_frames > 120:
            duration_per_frame_seconds = 0.1
        
        imageio.mimsave(gif_filename, frames, duration=duration_per_frame_seconds)
        print(f"Animated GIF successfully saved as {gif_filename} in the current directory.")

    # Temporary directory and its contents are automatically cleaned up upon exiting the 'with' block.
    print("Process complete.")

if __name__ == "__main__":
    print("Zillow Home Value Index (ZHVI) Animated GIF Generator")
    print("-" * 50)
    
    # Get user input for the ZIP code
    # Ensure this script is run in an environment that supports `input()` (e.g., a terminal)
    try:
        zip_code_to_animate = input("Enter the ZIP code for which you want to generate the animation: ").strip()
        if zip_code_to_animate:
            generate_zhvi_animation(zip_code_to_animate)
        else:
            print("No ZIP code entered. Exiting.")
    except RuntimeError:
        # This can happen in environments where stdin is not available (e.g. some GUI backends for matplotlib)
        print("\nCould not get user input. This script is best run from a command line or terminal.")
        print("You can also modify the script to call generate_zhvi_animation('YOUR_ZIP_CODE') directly.")
        # Example: generate_zhvi_animation("90210") 