import React, { useState } from 'react';
import axios from 'axios';
import { Container, Box, TextField, Button, Typography, Card, CardContent, Grid } from '@mui/material';

function App() {
  const [origin, setOrigin] = useState('');
  const [destination, setDestination] = useState('');
  const [quotes, setQuotes] = useState([]);

  const handleQuote = async () => {
    try {
      const response = await axios.post('http://localhost:5000/quote', {
        origin,
        destination,
      });
      setQuotes(response.data);
    } catch (error) {
      console.error('Error fetching quotes:', error);
    }
  };

  const requestLocation = () => {
    if (navigator.geolocation) {
      navigator.geolocation.getCurrentPosition(
        (position) => {
          const coords = `${position.coords.latitude}, ${position.coords.longitude}`;
          setOrigin(coords);
        },
        (error) => {
          console.error('Error fetching location:', error);
        }
      );
    }
  };

  return (
    <Container maxWidth="sm" style={{ marginTop: '50px' }}>
      <Typography variant="h4" component="h1" gutterBottom textAlign="center">
        Delivery Price Quotation
      </Typography>
      <Box display="flex" flexDirection="column" alignItems="center" gap={2}>
        <Button variant="contained" color="primary" onClick={requestLocation} style={{ marginBottom: '20px' }}>
          Use My Location
        </Button>
        <TextField
          fullWidth
          label="Destination"
          variant="outlined"
          value={destination}
          onChange={(e) => setDestination(e.target.value)}
        />
        <Button
          variant="contained"
          color="secondary"
          size="large"
          onClick={handleQuote}
          style={{ marginTop: '20px', width: '100%' }}
        >
          Get Quotes
        </Button>
      </Box>
      <Grid container spacing={2} style={{ marginTop: '40px' }}>
        {quotes.length > 0 &&
          quotes.map((quote, index) => (
            <Grid item xs={12} key={index}>
              <Card variant="outlined">
                <CardContent>
                  <Typography variant="h6">{quote.service}</Typography>
                  <Typography variant="body1">Price: ${quote.price.toFixed(2)}</Typography>
                </CardContent>
              </Card>
            </Grid>
          ))}
      </Grid>
    </Container>
  );
}

export default App;
