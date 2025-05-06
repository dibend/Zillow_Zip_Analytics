const express = require('express');
const axios = require('axios');
const { parse } = require('csv-parse');
const { finished } = require('stream/promises');
const path = require('path'); // To handle file paths

const app = express();
const PORT = process.env.PORT || 3001; // Port for the server

// --- Zillow Data Configuration ---
const ZILLOW_DATA_URL = 'https://files.zillowstatic.com/research/public_csvs/zhvi/Zip_zhvi_uc_sfrcondo_tier_0.33_0.67_sm_sa_month.csv';

// --- In-Memory Cache ---
const zillowCache = new Map(); // Key: ZIP Code (string), Value: { date: value, ... }

// --- Function to Load and Cache Data ---
async function loadAndCacheZillowData() {
    console.log(`Attempting to download Zillow data from ${ZILLOW_DATA_URL}...`);
    try {
        // Use axios to fetch the CSV data as a stream
        const response = await axios({
            method: 'get',
            url: ZILLOW_DATA_URL,
            responseType: 'stream',
        });

        console.log('Download successful. Parsing CSV data...');

        // Configure the CSV parser using csv-parse
        const parser = response.data.pipe(parse({
            columns: true, // Use first row as headers
            skip_empty_lines: true,
            trim: true,
            // Ensure correct data types
            cast: (value, context) => {
                if (context.column === 'RegionName') {
                    // Ensure ZIP is a 5-digit string
                    return String(value).padStart(5, '0');
                }
                // Check if header looks like a date and value is numeric
                if (/^\d{4}-\d{2}(-\d{2})?$/.test(context.header) && value !== '' && !isNaN(value)) {
                    return Number(value);
                }
                 // Return null for empty date values, otherwise keep original string
                 if (/^\d{4}-\d{2}(-\d{2})?$/.test(context.header) && value === '') {
                    return null;
                 }
                return value; // Keep other metadata as strings
            }
        }));

        let recordCount = 0;
        zillowCache.clear(); // Clear old cache

        // Process each row from the CSV stream
        parser.on('readable', () => {
            let record;
            while ((record = parser.read()) !== null) {
                const zipCode = record.RegionName;
                // Skip rows without a valid ZIP code
                if (!zipCode || zipCode === '00000') continue;

                const timeSeriesData = {};
                let hasData = false;
                // Extract date columns and their values
                for (const key in record) {
                     if (/^\d{4}-\d{2}(-\d{2})?$/.test(key) && record[key] !== null) {
                        timeSeriesData[key] = record[key];
                        hasData = true;
                    }
                }

                // Add to cache if data exists for the ZIP
                if (hasData) {
                    zillowCache.set(zipCode, timeSeriesData);
                    recordCount++;
                }
            }
        });

        // Handle parsing errors
        parser.on('error', (err) => {
            console.error('CSV Parsing Error:', err.message);
        });

        // Wait for the stream processing to complete
        await finished(parser);

        console.log(`Successfully parsed and cached data for ${recordCount} ZIP codes.`);

    } catch (error) {
        // Handle errors during download or processing
        console.error('Error fetching or processing Zillow data:', error.message);
        if (error.response) {
             console.error('Error Status:', error.response.status);
             console.error('Error Headers:', error.response.headers);
        }
        // Optional: Implement retry logic or specific error handling
    }
}

// --- Middleware ---
// Serve static files (like zip.html) from the 'public' directory
app.use(express.static(path.join(__dirname, 'public')));

// --- API Endpoint to Query Cache ---
// Provides the cached data to the frontend
app.get('/api/data/:zipcode', (req, res) => {
    const zipCode = String(req.params.zipcode).padStart(5, '0'); // Ensure 5-digit format

    if (zillowCache.has(zipCode)) {
        // Send JSON response if ZIP code found in cache
        res.json({
            zipCode: zipCode,
            data: zillowCache.get(zipCode)
        });
    } else {
        // Send 404 error if ZIP code not found
        res.status(404).json({ error: `Data not found for ZIP code ${zipCode}` });
    }
});

// --- Root Route ---
// Explicitly serve zip.html for the root path '/'
// This is technically handled by express.static, but can be explicit
app.get('/', (req, res) => {
  res.sendFile(path.join(__dirname, 'public', 'zip.html'));
});


// --- Start the Server and Load Data ---
async function startServer() {
    // Load data *before* the server starts accepting requests
    await loadAndCacheZillowData();

    // Start listening on the defined port
    app.listen(PORT, () => {
        console.log(`Server running on http://localhost:${PORT}`);
        console.log(`Serving zip.html and API.`);
        console.log(`Cache contains data for ${zillowCache.size} ZIP codes.`);
    });
}

// Run the server initialization function
startServer();
