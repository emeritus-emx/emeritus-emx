import axios from 'axios';

(async () => {
  try {
    const res = await axios.get('http://localhost:8000/health');
    console.log('STATUS', res.status);
    console.log('BODY', res.data);
  } catch (e) {
    console.error('ERROR', e.message);
    if (e.response) console.error('RESPONSE', e.response.status, e.response.data);
  }
})();
