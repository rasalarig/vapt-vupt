import React, { useEffect, useState } from 'react';
import axios from 'axios';
import {
  Container,
  Box,
  TextField,
  Button,
  Typography,
  Card,
  CardContent,
  Grid,
  FormControlLabel,
  Checkbox,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  OutlinedInput,
} from '@mui/material';

const API_BASE_URL = (process.env.REACT_APP_API_BASE_URL || 'http://localhost:5000').replace(/\/$/, '');
const EXPIRY_DEBUG_OFFSET_MS = 60 * 1000;

const PROVIDER_OPTIONS = [
  { value: 'lalamove', label: 'Lalamove' },
  { value: 'loggi', label: 'Loggi' },
];

const SERVICE_TYPE_OPTIONS = [
  { value: 'CAR', label: 'Carro (CAR)' },
  { value: 'MOTORCYCLE', label: 'Moto (MOTORCYCLE)' },
  { value: 'VAN', label: 'Van (VAN)' },
];

const MARKET_OPTIONS = [
  { value: 'BR', label: 'Brasil (BR)' },
  { value: 'MX', label: 'Mexico (MX)' },
  { value: 'SG', label: 'Singapura (SG)' },
  { value: 'HK', label: 'Hong Kong (HK)' },
];

const LANGUAGE_OPTIONS = [
  { value: 'pt_BR', label: 'Portugues (pt_BR)' },
  { value: 'en_US', label: 'Ingles (en_US)' },
  { value: 'es_MX', label: 'Espanhol (es_MX)' },
];

const SPECIAL_REQUEST_OPTIONS = [
  { value: 'LOADING_1DRIVER_MAX030MIN', label: 'Carga por 1 motorista (30 min)' },
  { value: 'LOADING_2DRIVER_MAX060MIN', label: 'Carga por 2 motoristas (60 min)' },
  { value: 'DOOR_TO_DOOR_1DRIVER', label: 'Retirada/entrega porta a porta' },
  { value: 'TAILBOARD_VEHICLE', label: 'Veiculo com plataforma elevatoria' },
];

const CATEGORY_OPTIONS = [
  { value: 'FOOD_DELIVERY', label: 'Entrega de comida' },
  { value: 'OFFICE_ITEM', label: 'Item de escritorio' },
  { value: 'ELECTRONICS', label: 'Eletronicos' },
  { value: 'GROCERY', label: 'Mercado' },
  { value: 'FLOWER', label: 'Flores' },
];

const HANDLING_OPTIONS = [
  { value: 'KEEP_UPRIGHT', label: 'Manter em pe' },
  { value: 'HANDLE_WITH_CARE', label: 'Frágil / com cuidado' },
  { value: 'REFRIGERATED', label: 'Refrigerado' },
  { value: 'DONT_STACK', label: 'Nao empilhar' },
];

const WEIGHT_OPTIONS = [
  { value: 'LESS_THAN_3_KG', label: 'Menos de 3 kg (LESS_THAN_3_KG)' },
  { value: 'BETWEEN_3_TO_10_KG', label: 'Entre 3 e 10 kg (BETWEEN_3_TO_10_KG)' },
  { value: 'BETWEEN_10_TO_20_KG', label: 'Entre 10 e 20 kg (BETWEEN_10_TO_20_KG)' },
  { value: 'MORE_THAN_20_KG', label: 'Mais de 20 kg (MORE_THAN_20_KG)' },
];

const getOptionLabel = (options, value) => options.find((option) => option.value === value)?.label || value;

const normalizeCep = (value) => (value || '').replace(/\D/g, '').slice(0, 8);

const buildAddressFromBase = (base, numero) => {
  if (!base) {
    return '';
  }

  const logradouro = (base.logradouro || '').trim();
  const bairro = (base.bairro || '').trim();
  const cidade = (base.cidade || '').trim();
  const uf = (base.uf || '').trim();
  const cep = (base.cep || '').trim();
  const numeroTexto = (numero || '').trim();

  const first = numeroTexto && logradouro ? `${logradouro}, ${numeroTexto}` : (logradouro || numeroTexto);
  const localParts = [bairro, cidade, uf].filter(Boolean).join(', ');

  let endereco = [first, localParts].filter(Boolean).join(', ');
  if (cep) {
    endereco = endereco ? `${endereco} - CEP ${cep}` : `CEP ${cep}`;
  }

  return endereco;
};

function App() {
  const [provider, setProvider] = useState('lalamove');
  const [cepOrigem, setCepOrigem] = useState('');
  const [numeroOrigem, setNumeroOrigem] = useState('');
  const [enderecoOrigem, setEnderecoOrigem] = useState('');
  const [origemBase, setOrigemBase] = useState(null);

  const [cepDestino, setCepDestino] = useState('');
  const [numeroDestino, setNumeroDestino] = useState('');
  const [enderecoDestino, setEnderecoDestino] = useState('');
  const [destinoBase, setDestinoBase] = useState(null);

  const [serviceType, setServiceType] = useState('CAR');
  const [language, setLanguage] = useState('pt_BR');
  const [market, setMarket] = useState('BR');
  const [cidadeUf, setCidadeUf] = useState('Sao Paulo, SP');
  const [isRouteOptimized, setIsRouteOptimized] = useState(true);
  const [quantity, setQuantity] = useState('1');
  const [weight, setWeight] = useState('LESS_THAN_3_KG');
  const [categories, setCategories] = useState(['FOOD_DELIVERY', 'OFFICE_ITEM']);
  const [handlingInstructions, setHandlingInstructions] = useState(['KEEP_UPRIGHT']);
  const [specialRequestsList, setSpecialRequestsList] = useState(['LOADING_1DRIVER_MAX030MIN']);

  const [quoteResult, setQuoteResult] = useState(null);
  const [quoteReceivedTs, setQuoteReceivedTs] = useState(null);
  const [showRawJson, setShowRawJson] = useState(false);
  const [errorMessage, setErrorMessage] = useState('');
  const [loading, setLoading] = useState(false);
  const [loadingCepOrigem, setLoadingCepOrigem] = useState(false);
  const [loadingCepDestino, setLoadingCepDestino] = useState(false);
  const [nowTs, setNowTs] = useState(Date.now());

  useEffect(() => {
    const timer = setInterval(() => setNowTs(Date.now()), 1000);
    return () => clearInterval(timer);
  }, []);

  const geocodeAddress = async (endereco, refCoords = null, base = null, numero = '') => {
    const ref = refCoords ? refCoords.split(',').map((value) => Number(value.trim())) : [];
    const refLat = Number.isFinite(ref[0]) ? ref[0] : null;
    const refLng = Number.isFinite(ref[1]) ? ref[1] : null;

    const response = await axios.post(`${API_BASE_URL}/geocode`, {
      endereco,
      cidade_uf: cidadeUf,
      ref_lat: refLat,
      ref_lng: refLng,
      logradouro: base?.logradouro || '',
      bairro: base?.bairro || '',
      cidade: base?.cidade || '',
      uf: base?.uf || '',
      cep: base?.cep || '',
      numero: numero || '',
    });

    const lat = response.data?.lat;
    const lng = response.data?.lng;

    if (typeof lat !== 'number' || typeof lng !== 'number') {
      throw new Error('Nao foi possivel converter endereco para coordenadas.');
    }

    return `${lat},${lng}`;
  };

  const applyLookupResult = (tipo, payload, numeroPreferido = '') => {
    const base = {
      logradouro: payload?.logradouro || '',
      bairro: payload?.bairro || '',
      cidade: payload?.cidade || '',
      uf: payload?.uf || '',
      cep: payload?.cep || '',
    };

    const numeroFinal = (numeroPreferido || payload?.numero || '').trim();
    const enderecoFinal = buildAddressFromBase(base, numeroFinal);

    if (tipo === 'origem') {
      setOrigemBase(base);
      setNumeroOrigem(numeroFinal);
      setEnderecoOrigem(enderecoFinal);
    } else {
      setDestinoBase(base);
      setNumeroDestino(numeroFinal);
      setEnderecoDestino(enderecoFinal);
    }
  };

  const fetchCep = async (tipo) => {
    const cepRaw = tipo === 'origem' ? cepOrigem : cepDestino;
    const numeroAtual = tipo === 'origem' ? numeroOrigem : numeroDestino;
    const cep = normalizeCep(cepRaw);

    if (cep.length !== 8) {
      setErrorMessage('Informe um CEP valido com 8 digitos.');
      return;
    }

    try {
      setErrorMessage('');
      if (tipo === 'origem') {
        setLoadingCepOrigem(true);
      } else {
        setLoadingCepDestino(true);
      }

      const response = await axios.get(`${API_BASE_URL}/cep/${cep}`);
      applyLookupResult(tipo, response.data, numeroAtual);
    } catch (error) {
      const backendError = error.response?.data?.error;
      setErrorMessage(backendError || `Erro ao buscar CEP: ${error.message}`);
    } finally {
      if (tipo === 'origem') {
        setLoadingCepOrigem(false);
      } else {
        setLoadingCepDestino(false);
      }
    }
  };

  const handleNumeroChange = (tipo, value) => {
    if (tipo === 'origem') {
      setNumeroOrigem(value);
      if (origemBase) {
        setEnderecoOrigem(buildAddressFromBase(origemBase, value));
      }
    } else {
      setNumeroDestino(value);
      if (destinoBase) {
        setEnderecoDestino(buildAddressFromBase(destinoBase, value));
      }
    }
  };

  const handleQuote = async () => {
    setErrorMessage('');
    setQuoteResult(null);

    if (!enderecoOrigem || !enderecoDestino) {
      setErrorMessage('Informe origem e destino para cotar.');
      return;
    }

    try {
      setLoading(true);

      const origemCoords = await geocodeAddress(enderecoOrigem, null, origemBase, numeroOrigem);
      const destinoCoords = await geocodeAddress(enderecoDestino, origemCoords, destinoBase, numeroDestino);

      const response = await axios.post(`${API_BASE_URL}/cotacao`, {
        provider,
        endereco_origem: origemCoords,
        endereco_destino: destinoCoords,
        endereco_origem_label: enderecoOrigem,
        endereco_destino_label: enderecoDestino,
        service_type: serviceType,
        language,
        market,
        is_route_optimized: isRouteOptimized,
        special_requests: specialRequestsList,
        item: {
          quantity,
          weight,
          categories,
          handlingInstructions,
        },
      });

      setQuoteResult(response.data);
      setQuoteReceivedTs(Date.now());
      setShowRawJson(false);
    } catch (error) {
      const backendError = error.response?.data?.error;
      const details = backendError && typeof backendError === 'object'
        ? `\nDetalhes: ${JSON.stringify(backendError)}`
        : '';

      setErrorMessage(
        typeof backendError === 'string'
          ? `${backendError}${details}`
          : `Erro ao buscar cotacao: ${error.message}${details}`
      );
    } finally {
      setLoading(false);
    }
  };

  const formatCurrency = (value, currency = 'BRL') => {
    if (value === undefined || value === null || value === '') {
      return '-';
    }

    const numeric = Number(String(value).replace(',', '.'));
    if (Number.isNaN(numeric)) {
      return `${value} ${currency}`;
    }

    return new Intl.NumberFormat('pt-BR', {
      style: 'currency',
      currency,
    }).format(numeric);
  };

  const formatDateTime = (value) => {
    const date = parseApiDate(value, quoteReceivedTs);
    if (!date) {
      return '-';
    }

    return date.toLocaleString('pt-BR');
  };

  const formatTimeOnly = (value) => {
    const date = parseApiDate(value, quoteReceivedTs);
    if (!date) {
      return '-';
    }

    return date.toLocaleTimeString('pt-BR');
  };

  const parseApiDate = (value, referenceTs = null) => {
    if (!value || typeof value !== 'string') {
      return null;
    }

    const utcDate = new Date(value);
    const hasUtcMarker = value.endsWith('Z') || value.includes('+');

    // Fallback para APIs que devolvem horario local com sufixo UTC.
    let localFallback = null;
    if (hasUtcMarker) {
      const withoutZ = value.replace(/Z$/, '');
      const localDate = new Date(withoutZ);
      if (!Number.isNaN(localDate.getTime())) {
        localFallback = localDate;
      }
    }

    if (Number.isNaN(utcDate.getTime()) && !localFallback) {
      return null;
    }

    if (!localFallback) {
      return utcDate;
    }

    if (Number.isNaN(utcDate.getTime())) {
      return localFallback;
    }

    if (!referenceTs) {
      return utcDate;
    }

    const utcDelta = Math.abs(utcDate.getTime() - referenceTs);
    const localDelta = Math.abs(localFallback.getTime() - referenceTs);

    // Escolhe o horario mais proximo do momento da resposta.
    return localDelta < utcDelta ? localFallback : utcDate;
  };

  const distanceToKm = (distanceValue, distanceUnit) => {
    if (!distanceValue) {
      return null;
    }

    const numeric = Number(distanceValue);
    if (Number.isNaN(numeric)) {
      return null;
    }

    if ((distanceUnit || '').toLowerCase() === 'm') {
      return numeric / 1000;
    }

    return numeric;
  };

  const formatCountdown = (targetIso) => {
    const targetDate = parseApiDate(targetIso, quoteReceivedTs);
    if (!targetDate) {
      return '-';
    }

    const target = targetDate.getTime();

    const remainingMs = target - nowTs;
    if (remainingMs <= 0) {
      return 'Expirada';
    }

    const totalSeconds = Math.floor(remainingMs / 1000);
    const hours = String(Math.floor(totalSeconds / 3600)).padStart(2, '0');
    const minutes = String(Math.floor((totalSeconds % 3600) / 60)).padStart(2, '0');
    const seconds = String(totalSeconds % 60).padStart(2, '0');
    return `${hours}:${minutes}:${seconds}`;
  };

  const getEstimatedDeliveryData = () => {
    if (!quoteResult?.data) {
      return {
        estimatedMinutes: null,
        pickupIso: null,
        dropoffIso: null,
      };
    }

    const distanceKm = distanceToKm(quoteResult.data?.distance?.value, quoteResult.data?.distance?.unit);
    const pickupIso = quoteResult.data?.scheduleAt || null;

    if (!distanceKm || !pickupIso) {
      return {
        estimatedMinutes: null,
        pickupIso,
        dropoffIso: null,
      };
    }

    const estimatedMinutes = Math.max(15, Math.round((distanceKm / 25) * 60 + 10));
    const pickupDate = parseApiDate(pickupIso, quoteReceivedTs);
    const pickupTime = pickupDate ? pickupDate.getTime() : NaN;
    const dropoffIso = Number.isNaN(pickupTime)
      ? null
      : new Date(pickupTime + estimatedMinutes * 60 * 1000).toISOString();

    return {
      estimatedMinutes,
      pickupIso,
      dropoffIso,
    };
  };

  const deliveryData = getEstimatedDeliveryData();
  const distanceKm = quoteResult?.data
    ? distanceToKm(quoteResult.data?.distance?.value, quoteResult.data?.distance?.unit)
    : null;
  const expiresDate = parseApiDate(quoteResult?.data?.expiresAt, quoteReceivedTs);
  const scheduleDate = parseApiDate(quoteResult?.data?.scheduleAt, quoteReceivedTs);
  const adjustedExpiresDate = expiresDate
    ? new Date(expiresDate.getTime() + EXPIRY_DEBUG_OFFSET_MS)
    : null;
  const validitySeconds = expiresDate && scheduleDate
    ? Math.max(0, Math.floor((expiresDate.getTime() - scheduleDate.getTime()) / 1000))
    : null;
  const isQuoteExpired = adjustedExpiresDate ? adjustedExpiresDate.getTime() <= nowTs : false;

  return (
    <Container maxWidth="lg" style={{ marginTop: '40px', marginBottom: '50px' }}>
      <Typography variant="h4" component="h1" gutterBottom textAlign="center">
        Cotacao de Transportadoras
      </Typography>

      <Grid container spacing={3}>
        <Grid item xs={12} md={6}>
          <Card variant="outlined">
            <CardContent>
              <Typography variant="h6" gutterBottom>
                Origem
              </Typography>

              <Box display="flex" flexDirection="column" gap={2}>
                <Grid container spacing={2}>
                  <Grid item xs={8}>
                    <TextField
                      fullWidth
                      label="CEP origem"
                      value={cepOrigem}
                      onChange={(e) => setCepOrigem(normalizeCep(e.target.value))}
                      placeholder="00000000"
                    />
                  </Grid>
                  <Grid item xs={4}>
                    <Button
                      fullWidth
                      variant="outlined"
                      style={{ height: '56px' }}
                      onClick={() => fetchCep('origem')}
                      disabled={loadingCepOrigem}
                    >
                      {loadingCepOrigem ? 'Buscando...' : 'Buscar CEP'}
                    </Button>
                  </Grid>
                </Grid>

                <TextField
                  fullWidth
                  label="Numero origem"
                  value={numeroOrigem}
                  onChange={(e) => handleNumeroChange('origem', e.target.value)}
                  helperText="Altere o numero e o endereco completo atualiza automaticamente quando origem vier de CEP."
                />

                <TextField
                  fullWidth
                  label="Endereco completo origem"
                  value={enderecoOrigem}
                  onChange={(e) => {
                    setEnderecoOrigem(e.target.value);
                    setOrigemBase(null);
                  }}
                />
              </Box>
            </CardContent>
          </Card>
        </Grid>

        <Grid item xs={12} md={6}>
          <Card variant="outlined">
            <CardContent>
              <Typography variant="h6" gutterBottom>
                Destino
              </Typography>

              <Box display="flex" flexDirection="column" gap={2}>
                <Grid container spacing={2}>
                  <Grid item xs={8}>
                    <TextField
                      fullWidth
                      label="CEP destino"
                      value={cepDestino}
                      onChange={(e) => setCepDestino(normalizeCep(e.target.value))}
                      placeholder="00000000"
                    />
                  </Grid>
                  <Grid item xs={4}>
                    <Button
                      fullWidth
                      variant="outlined"
                      style={{ height: '56px' }}
                      onClick={() => fetchCep('destino')}
                      disabled={loadingCepDestino}
                    >
                      {loadingCepDestino ? 'Buscando...' : 'Buscar CEP'}
                    </Button>
                  </Grid>
                </Grid>

                <TextField
                  fullWidth
                  label="Numero destino"
                  value={numeroDestino}
                  onChange={(e) => handleNumeroChange('destino', e.target.value)}
                  helperText="Altere o numero e o endereco completo atualiza automaticamente quando destino vier de CEP."
                />

                <TextField
                  fullWidth
                  label="Endereco completo destino"
                  value={enderecoDestino}
                  onChange={(e) => {
                    setEnderecoDestino(e.target.value);
                    setDestinoBase(null);
                  }}
                />
              </Box>
            </CardContent>
          </Card>
        </Grid>
      </Grid>

      <Card variant="outlined" style={{ marginTop: '24px' }}>
        <CardContent>
          <Typography variant="h6" gutterBottom>
            Parametros da Cotacao
          </Typography>

          <Grid container spacing={2}>
            <Grid item xs={12} sm={6} md={3}>
              <FormControl fullWidth>
                <InputLabel id="provider-label">Transportadora</InputLabel>
                <Select
                  labelId="provider-label"
                  value={provider}
                  label="Transportadora"
                  onChange={(e) => setProvider(e.target.value)}
                >
                  {PROVIDER_OPTIONS.map((option) => (
                    <MenuItem key={option.value} value={option.value}>{option.label}</MenuItem>
                  ))}
                </Select>
              </FormControl>
            </Grid>
            <Grid item xs={12} sm={6} md={3}>
              <FormControl fullWidth>
                <InputLabel id="service-type-label">Service Type</InputLabel>
                <Select
                  labelId="service-type-label"
                  value={serviceType}
                  label="Service Type"
                  onChange={(e) => setServiceType(e.target.value)}
                >
                  {SERVICE_TYPE_OPTIONS.map((option) => (
                    <MenuItem key={option.value} value={option.value}>{option.label}</MenuItem>
                  ))}
                </Select>
              </FormControl>
            </Grid>
            <Grid item xs={12} sm={6} md={3}>
              <FormControl fullWidth>
                <InputLabel id="market-label">Market</InputLabel>
                <Select
                  labelId="market-label"
                  value={market}
                  label="Market"
                  onChange={(e) => setMarket(e.target.value)}
                >
                  {MARKET_OPTIONS.map((option) => (
                    <MenuItem key={option.value} value={option.value}>{option.label}</MenuItem>
                  ))}
                </Select>
              </FormControl>
            </Grid>
            <Grid item xs={12} sm={6} md={3}>
              <FormControl fullWidth>
                <InputLabel id="language-label">Idioma</InputLabel>
                <Select
                  labelId="language-label"
                  value={language}
                  label="Idioma"
                  onChange={(e) => setLanguage(e.target.value)}
                >
                  {LANGUAGE_OPTIONS.map((option) => (
                    <MenuItem key={option.value} value={option.value}>{option.label}</MenuItem>
                  ))}
                </Select>
              </FormControl>
            </Grid>
            <Grid item xs={12} sm={6} md={3}>
              <TextField
                fullWidth
                label="Cidade/UF de referencia"
                value={cidadeUf}
                onChange={(e) => setCidadeUf(e.target.value)}
              />
            </Grid>

            <Grid item xs={12}>
              <FormControl fullWidth>
                <InputLabel id="special-requests-label">Special Requests</InputLabel>
                <Select
                  multiple
                  labelId="special-requests-label"
                  value={specialRequestsList}
                  onChange={(e) => {
                    const value = e.target.value;
                    setSpecialRequestsList(typeof value === 'string' ? value.split(',') : value);
                  }}
                  input={<OutlinedInput label="Special Requests" />}
                  renderValue={(selected) => selected.map((value) => getOptionLabel(SPECIAL_REQUEST_OPTIONS, value)).join(', ')}
                >
                  {SPECIAL_REQUEST_OPTIONS.map((option) => (
                    <MenuItem key={option.value} value={option.value}>{option.label}</MenuItem>
                  ))}
                </Select>
              </FormControl>
            </Grid>

            <Grid item xs={12} sm={4}>
              <TextField fullWidth label="Quantidade" value={quantity} onChange={(e) => setQuantity(e.target.value)} />
            </Grid>
            <Grid item xs={12} sm={4}>
              <FormControl fullWidth>
                <InputLabel id="weight-label">Peso</InputLabel>
                <Select
                  labelId="weight-label"
                  value={weight}
                  label="Peso"
                  onChange={(e) => setWeight(e.target.value)}
                >
                  {WEIGHT_OPTIONS.map((option) => (
                    <MenuItem key={option.value} value={option.value}>{option.label}</MenuItem>
                  ))}
                </Select>
              </FormControl>
            </Grid>
            <Grid item xs={12} sm={4}>
              <FormControlLabel
                control={<Checkbox checked={isRouteOptimized} onChange={(e) => setIsRouteOptimized(e.target.checked)} />}
                label="Otimizar rota"
              />
            </Grid>

            <Grid item xs={12}>
              <FormControl fullWidth>
                <InputLabel id="categories-label">Categorias</InputLabel>
                <Select
                  multiple
                  labelId="categories-label"
                  value={categories}
                  onChange={(e) => {
                    const value = e.target.value;
                    setCategories(typeof value === 'string' ? value.split(',') : value);
                  }}
                  input={<OutlinedInput label="Categorias" />}
                  renderValue={(selected) => selected.map((value) => getOptionLabel(CATEGORY_OPTIONS, value)).join(', ')}
                >
                  {CATEGORY_OPTIONS.map((option) => (
                    <MenuItem key={option.value} value={option.value}>{option.label}</MenuItem>
                  ))}
                </Select>
              </FormControl>
            </Grid>
            <Grid item xs={12}>
              <FormControl fullWidth>
                <InputLabel id="handling-label">Instrucoes de manuseio</InputLabel>
                <Select
                  multiple
                  labelId="handling-label"
                  value={handlingInstructions}
                  onChange={(e) => {
                    const value = e.target.value;
                    setHandlingInstructions(typeof value === 'string' ? value.split(',') : value);
                  }}
                  input={<OutlinedInput label="Instrucoes de manuseio" />}
                  renderValue={(selected) => selected.map((value) => getOptionLabel(HANDLING_OPTIONS, value)).join(', ')}
                >
                  {HANDLING_OPTIONS.map((option) => (
                    <MenuItem key={option.value} value={option.value}>{option.label}</MenuItem>
                  ))}
                </Select>
              </FormControl>
            </Grid>
          </Grid>

          <Button
            variant="contained"
            color="secondary"
            size="large"
            onClick={handleQuote}
            style={{ marginTop: '20px', width: '100%' }}
            disabled={loading}
          >
            {loading ? 'Consultando...' : 'Cotar viagem'}
          </Button>
        </CardContent>
      </Card>

      {errorMessage && (
        <Typography color="error" style={{ marginTop: '20px' }}>
          {errorMessage}
        </Typography>
      )}

      {quoteResult && (
        <Grid container spacing={2} style={{ marginTop: '20px' }}>
          <Grid item xs={12}>
            <Card variant="outlined">
              <CardContent>
                <Typography variant="h6" gutterBottom>
                  Resumo da cotacao
                </Typography>

                <Grid container spacing={2}>
                  <Grid item xs={12} sm={6} md={3}>
                    <Typography variant="subtitle2">Transportadora</Typography>
                    <Typography variant="h6">{quoteResult?.provider || provider.toUpperCase()}</Typography>
                  </Grid>
                  <Grid item xs={12} sm={6} md={3}>
                    <Typography variant="subtitle2">Valor total</Typography>
                    <Typography variant="h6">
                      {formatCurrency(quoteResult?.data?.priceBreakdown?.total, quoteResult?.data?.priceBreakdown?.currency || 'BRL')}
                    </Typography>
                  </Grid>
                  <Grid item xs={12} sm={6} md={3}>
                    <Typography variant="subtitle2">Servico</Typography>
                    <Typography variant="h6">{quoteResult?.data?.serviceType || '-'}</Typography>
                  </Grid>
                  <Grid item xs={12} sm={6} md={3}>
                    <Typography variant="subtitle2">Distancia</Typography>
                    <Typography variant="h6">
                      {distanceKm !== null ? `${distanceKm.toFixed(2)} km` : '-'}
                    </Typography>
                  </Grid>
                  <Grid item xs={12} sm={6} md={3}>
                    <Typography variant="subtitle2">Prazo da cotacao</Typography>
                    <Typography variant="h6">{formatCountdown(adjustedExpiresDate?.toISOString())}</Typography>
                  </Grid>
                  <Grid item xs={12} sm={6} md={3}>
                    <Typography variant="subtitle2">Validade da API</Typography>
                    <Typography variant="h6">
                      {validitySeconds !== null ? `${validitySeconds}s` : '-'}
                    </Typography>
                  </Grid>
                  <Grid item xs={12} sm={6} md={3}>
                    <Typography variant="subtitle2">Tempo de entrega (estimado)</Typography>
                    <Typography variant="h6">
                      {deliveryData.estimatedMinutes !== null ? `${deliveryData.estimatedMinutes} min` : '-'}
                    </Typography>
                  </Grid>
                  <Grid item xs={12} sm={6} md={3}>
                    <Typography variant="subtitle2">Inicio da coleta</Typography>
                    <Typography variant="h6">{formatTimeOnly(deliveryData.pickupIso)}</Typography>
                  </Grid>
                  <Grid item xs={12} sm={6} md={3}>
                    <Typography variant="subtitle2">Fim da entrega</Typography>
                    <Typography variant="h6">{formatTimeOnly(deliveryData.dropoffIso)}</Typography>
                  </Grid>
                  <Grid item xs={12} sm={6} md={3}>
                    <Typography variant="subtitle2">Expira em</Typography>
                    <Typography variant="h6">{formatDateTime(adjustedExpiresDate?.toISOString())}</Typography>
                  </Grid>
                </Grid>

                <Typography variant="caption" color="text.secondary" style={{ display: 'block', marginTop: '8px' }}>
                  Modo teste sandbox: prazo exibido com +1 minuto.
                </Typography>

                {isQuoteExpired && (
                  <Box style={{ marginTop: '12px' }}>
                    <Typography color="error" variant="body2" style={{ marginBottom: '8px' }}>
                      Cotacao expirada. No sandbox da Lalamove a validade pode ser de poucos segundos.
                    </Typography>
                    <Button variant="outlined" onClick={handleQuote} disabled={loading}>
                      Atualizar cotacao
                    </Button>
                  </Box>
                )}

                <Button
                  variant="text"
                  style={{ marginTop: '16px' }}
                  onClick={() => setShowRawJson((prev) => !prev)}
                >
                  {showRawJson ? 'Ocultar JSON completo' : 'Ver JSON completo'}
                </Button>

                {showRawJson && (
                  <pre style={{ whiteSpace: 'pre-wrap', margin: 0 }}>{JSON.stringify(quoteResult, null, 2)}</pre>
                )}
              </CardContent>
            </Card>
          </Grid>
        </Grid>
      )}
    </Container>
  );
}

export default App;
