# Fakturan.nu API 2 — Documentation

## ⚠️ Important Rule: Sandbox vs Production URLs

> **Sandbox and Production use DIFFERENT base URLs. Always make sure you are using the correct one for your environment.**

| Environment | Base URL |
| --- | --- |
| **Sandbox** (testing) | `https://sandbox.fakturan.nu` |
| **Production** (live) | `https://www.fakturan.nu` |

- Use **sandbox** for development, integration testing, and experiments. Data here is not real and may be reset.
- Use **production** only when your integration is ready for real clients and real invoices.
- API keys are **not shared** between sandbox and production — you must generate a separate key for each environment.

---

## Getting Started

### General Information

#### Authentication & Content-Type

In order to authenticate to the API you will be using **HTTP Basic Auth** together with your generated `api-key-ID` and `password`. Data is transferred via JSON-body.

- Header: `Content-Type: application/json`
- Auth: HTTP Basic (`api-key-id:api-key-password`)

#### Statuses & Error Codes

The API will answer with different status codes depending on various scenarios. The status codes can be used in order to know how to handle the response.

**Successful requests**

| Code | Meaning |
| --- | --- |
| `200` | Everything is OK |
| `201` | Resource created |
| `204` | Resource updated (nothing returned) |

**Unsuccessful requests**

| Code | Meaning |
| --- | --- |
| `400` | Bad request |
| `403` | Forbidden |
| `404` | Resource not found |
| `422` | Validation error |
| `500` | Internal server error |

---

## Resources

### Clients

#### `GET /api/v2/clients` — List clients

**Params**

| Name | Description |
| --- | --- |
| `number` | Filter by client number |
| `org_number` | Filter by client org. number |
| `email` | Filter by client email |
| `sort` | Allowed sort fields: `number`, `name`. Direction prefix: `+` ASC, `-` DESC. Example: `sort=+field,-secondary_field` |

**Example**

```http
GET /api/v2/clients
```

```json
200
{
  "data": [
    {
      "id": 3,
      "number": 1,
      "name": "Google Inc",
      "first_name": "",
      "last_name": "",
      "email": "",
      "fax": "",
      "phone": "",
      "home_phone": "",
      "mobile_phone": "",
      "client_type": "company",
      "org_number": "556677-8899",
      "settings": {
        "currency": "USD",
        "discount": 0,
        "email_attach_pdf": false,
        "invoice_days": 30,
        "invoice_delivery_method": "email",
        "invoice_template": "croatia",
        "locale": "sv",
        "prices_inc_tax": "no",
        "show_product_code": false,
        "tax": 25
      },
      "address": {
        "street_address": "1600 Amphitheatre Parkway",
        "care_of": "",
        "zip_code": "94043",
        "city": "Mountain View",
        "country": "SE"
      }
    }
  ],
  "paging": {
    "total_pages": 1,
    "current_page": 1,
    "next": null,
    "previous": null
  }
}
```

---

#### `GET /api/v2/clients/:id` — Show a client

**Example**

```http
GET /api/v2/clients/4
```

```json
200
{
  "data": {
    "id": 4,
    "number": 1,
    "name": "Google Inc",
    "first_name": "",
    "last_name": "",
    "email": "",
    "fax": "",
    "phone": "",
    "home_phone": "",
    "mobile_phone": "",
    "client_type": "company",
    "org_number": "556677-8899",
    "settings": {
      "currency": "USD",
      "discount": 0,
      "email_attach_pdf": false,
      "invoice_days": 30,
      "invoice_delivery_method": "email",
      "invoice_template": "croatia",
      "locale": "sv",
      "prices_inc_tax": "no",
      "show_product_code": false,
      "tax": 25
    },
    "address": {
      "street_address": "1600 Amphitheatre Parkway",
      "care_of": "",
      "zip_code": "94043",
      "city": "Mountain View",
      "country": "SE"
    }
  }
}
```

---

#### `POST /api/v2/clients` — Create a client

**Params**

| Name | Description |
| --- | --- |
| `number` | Client number |
| `first_name` | Must be present if client is an individual |
| `last_name` | Must be present if client is an individual |
| `email` | Must be valid email if used |
| `company` | Must be present unless client is an individual |
| `phone` | |
| `home_phone` | |
| `mobile_phone` | |
| `fax` | |
| `org_number` | |
| `client_type` | Is the client an individual (not a business)? One of: `company`, `individual` (defaults to `company`) |
| `web` | |
| `vat_number` | |
| `gln` | Global Location Number (e-invoice address) |

**Settings (Hash)**

| Name | Description |
| --- | --- |
| `settings[invoice_delivery_method]` | One of: `email`, `email_and_sms`, `letter`, `e_invoice` |
| `settings[e_invoice]` | Boolean. If possible, the invoice will be sent as an e-invoice |
| `settings[invoice_days]` | Default for new invoices to this client. Defaults to global setting |
| `settings[locale]` | Default for new invoices to this client. Defaults to global setting |
| `settings[currency]` | Default for new invoices to this client. Defaults to global setting |
| `settings[email_attach_pdf]` | Boolean. Attach PDF when sending invoices by email. Useful if the recipient needs the PDF for automatic scanning |

**Address (Hash)**

| Name | Description |
| --- | --- |
| `address[street_address]` | |
| `address[care_of]` | Printed as the first line in the address. No "care of" prefix is added by the application — you have to add it yourself. The field can also be used for other purposes, e.g. "Att." |
| `address[zip_code]` | |
| `address[city]` | |
| `address[country]` | |

**Example — success**

```http
POST /api/v2/clients
```

```json
{
  "first_name": "Nils",
  "last_name": "Eriksson",
  "address": {
    "street_address": "Testvägen",
    "care_of": "Någon",
    "zip_code": "12345",
    "city": "Karlstad",
    "country": "SE"
  },
  "mobile_phone": "46701234567",
  "email": "test@test.com",
  "fax": "",
  "phone": "070 751 51 66",
  "home_phone": "46701234567",
  "client_type": "individual",
  "org_number": "8001010043"
}
```

```json
201
{
  "data": {
    "id": 2,
    "number": 1,
    "name": "Nils Eriksson",
    "first_name": "Nils",
    "last_name": "Eriksson",
    "email": "test@test.com",
    "fax": "",
    "phone": "070 751 51 66",
    "home_phone": "46701234567",
    "mobile_phone": "46701234567",
    "client_type": "individual",
    "org_number": "8001010043",
    "settings": {
      "currency": "SEK",
      "discount": 0,
      "email_attach_pdf": false,
      "invoice_days": 30,
      "invoice_delivery_method": "email",
      "invoice_template": "croatia",
      "locale": "sv",
      "prices_inc_tax": "no",
      "show_product_code": false,
      "tax": 25
    },
    "address": {
      "street_address": "Testvägen",
      "care_of": "Någon",
      "zip_code": "12345",
      "city": "Karlstad",
      "country": "SE"
    }
  }
}
```

**Example — validation error**

```http
POST /api/v2/clients
```

```json
{ "company": "" }
```

```json
422
{
  "errors": {
    "company": [
      { "error": "blank" }
    ]
  }
}
```

---

#### `PUT /api/v2/clients/:id` — Update a client

Accepts the same parameters as **Create a client**.

**Example**

```http
PUT /api/v2/clients/10
```

```json
{ "company": "After" }
```

```
204
```

---

### Products

#### `GET /api/v2/products` — List products

**Params**

| Name | Description |
| --- | --- |
| `product_code` | Filter by `product_code` |
| `name` | Filter by product name |
| `sort` | Allowed sort fields: `name`, `product_code`, `price`. Direction prefix: `+` ASC, `-` DESC. Example: `sort=+field,-secondary_field` |

Pagination is supported via `page` and `per_page` query parameters.

**Example**

```http
GET /api/v2/products
```

```json
200
{
  "data": [
    {
      "id": 3,
      "product_code": "XYZ",
      "name": "My product",
      "unit": "kg",
      "price": "150.0",
      "price_inc_tax": "187.5",
      "tax": 25
    }
  ],
  "paging": {
    "total_pages": 1,
    "current_page": 1,
    "next": null,
    "previous": null
  }
}
```

**Example — with pagination**

```http
GET /api/v2/products?page=2&per_page=10
```

```json
200
{
  "data": [ /* ... */ ],
  "paging": {
    "total_pages": 2,
    "current_page": 2,
    "next": null,
    "previous": "http://www.example.com/api/v2/products?page=1&per_page=15"
  }
}
```

---

#### `GET /api/v2/products/:id` — Show a product

**Example**

```http
GET /api/v2/products/20
```

```json
200
{
  "data": {
    "id": 20,
    "product_code": "XYZ",
    "name": "My product",
    "unit": "kg",
    "price": "150.0",
    "price_inc_tax": "187.5",
    "tax": 25
  }
}
```

---

#### `POST /api/v2/products` — Create a product

**Params**

| Name | Description |
| --- | --- |
| `name` | Name of the product or service (required) |
| `unit` | |
| `price` | |
| `tax` | |
| `product_code` | Max length 30 |

**Example — success**

```http
POST /api/v2/products
```

```json
{
  "name": "Test",
  "price": "150.3",
  "tax": 12,
  "unit": "h",
  "product_code": "XYZ"
}
```

```json
201
{
  "data": {
    "id": 1,
    "product_code": "XYZ",
    "name": "Test",
    "unit": "h",
    "price": "150.3",
    "price_inc_tax": "168.34",
    "tax": 12
  }
}
```

**Example — validation error**

```http
POST /api/v2/products
```

```json
{ "name": "" }
```

```json
422
{
  "errors": {
    "name": [
      { "error": "blank" }
    ]
  }
}
```

---

#### `PUT /api/v2/products/:id` — Update a product

Same params as **Create a product**.

**Example**

```http
PUT /api/v2/products/24
```

```json
{ "name": "After" }
```

```
204
```

---

#### `DELETE /api/v2/products/:id` — Destroy a product

**Example**

```http
DELETE /api/v2/products/2
```

```
204
```

---

### Invoices

#### `GET /api/v2/invoices` — List invoices

**Params**

| Name | Description |
| --- | --- |
| `number` | Filter by number |
| `client_id` | Filter by `client_id` |
| `start_date` | Filter invoices from `start_date` to `end_date` (or today's date if `end_date` is omitted) |
| `end_date` | Filter invoices from `start_date` (or from the beginning of time if `start_date` is omitted) to `end_date` |
| `sort` | Allowed sort fields: `number`, `date`. Direction prefix: `+` ASC, `-` DESC. Example: `sort=+field,-secondary_field` |

---

#### `GET /api/v2/invoices/:id` — Show an invoice

**Example**

```http
GET /api/v2/invoices/10
```

```json
200
{
  "data": {
    "id": 10,
    "number": 1,
    "date": "2021-01-25",
    "client_id": 9,
    "days": 30,
    "our_reference": "",
    "your_reference": "",
    "sent": false,
    "paid_at": null,
    "locale": "sv",
    "currency": "SEK",
    "settings": {
      "invoice_template": "croatia",
      "prices_inc_tax": "no",
      "show_product_code": false
    },
    "sum": "1250.0",
    "net": "1000.0",
    "tax": "250.0",
    "tax_details": { "25": "250.0" },
    "address": {
      "name": "Google Inc",
      "street_address": "1600 Amphitheatre Parkway",
      "care_of": "",
      "zip_code": "940 43",
      "city": "Mountain View",
      "country": "SE"
    },
    "rows": [
      {
        "id": 13,
        "product_id": 0,
        "discount": 0,
        "amount": "5.0",
        "text": "",
        "product_code": null,
        "product_name": "product",
        "product_unit": "st",
        "product_price": "200.0",
        "product_tax": 25,
        "text_row": false,
        "sort_order": 0,
        "tax_deductible": false
      }
    ]
  }
}
```

---

#### `POST /api/v2/invoices` — Create an invoice

**Params**

| Name | Description |
| --- | --- |
| `number` | Invoice number. Defaults to +1 of highest number currently in account |
| `date` | Date string in the format `yyyy-mm-dd` |
| `client_id` | Id of existing client. `client_id` OR `client` is required |
| `days` | Number of days from `date` that invoice payment is due |
| `our_reference` | Name of person who acts as reference at sender's company |
| `your_reference` | Name of person who acts as reference at receiver's company |
| `locale` | One of: `sv`, `en`, `da`, `nb` |
| `currency` | |

**Settings (Hash)**

| Name | Description |
| --- | --- |
| `settings[invoice_template]` | One of: `urban`, `clean`, `iconic`, `foxy`, `static`, `original`, `croatia` |
| `settings[show_product_code]` | Boolean. Should the invoice show the product code column? |

**Client (Hash)** — See **Create client** for full parameter list.

> Note: it is **not** possible to update a client on an invoice update — only create a client on invoice create.

**Rows (Array of nested elements)**

| Name | Description |
| --- | --- |
| `rows[id]` | |
| `rows[product_id]` | |
| `rows[discount]` | Discount in % |
| `rows[amount]` | How many units of this item? May be fractional (`"1.5"`) |
| `rows[text]` | Max length 255 |
| `rows[product_code]` | Max length 30 |
| `rows[product_name]` | Max length 255 |
| `rows[product_unit]` | Max length 30 |
| `rows[product_price]` | Price of this item. May be fractional (`"9.95"`) |
| `rows[product_tax]` | One of: `25`, `12`, `6`, `0` |
| `rows[text_row]` | Boolean. Show this row as purely text? |
| `rows[sort_order]` | |

**Example — create invoice for existing client**

```http
POST /api/v2/invoices
```

```json
{
  "client_id": 1,
  "rows": [
    { "product_name": "My product",   "product_tax": 25, "product_price": "100", "amount": "10" },
    { "product_name": "My product 2", "product_tax": 12, "product_price": "100", "amount": "10 st" },
    { "text": "Some arbitrary text", "text_row": true }
  ]
}
```

```json
201
{
  "data": {
    "id": 1,
    "number": 1,
    "date": "2021-01-25",
    "client_id": 1,
    "days": 30,
    "our_reference": "",
    "your_reference": "",
    "sent": false,
    "paid_at": null,
    "locale": "sv",
    "currency": "SEK",
    "settings": {
      "invoice_template": "croatia",
      "prices_inc_tax": "no",
      "show_product_code": false
    },
    "sum": "2370.0",
    "net": "2000.0",
    "tax": "370.0",
    "tax_details": { "25": "250.0", "12": "120.0" },
    "address": {
      "name": "Google Inc",
      "street_address": "1600 Amphitheatre Parkway",
      "care_of": "",
      "zip_code": "940 43",
      "city": "Mountain View",
      "country": "SE"
    },
    "rows": [
      { "id": 1, "product_id": 0, "discount": 0, "amount": "10.0", "text": "", "product_code": null, "product_name": "My product",   "product_unit": "", "product_price": "100.0", "product_tax": 25, "text_row": false, "sort_order": 0, "tax_deductible": false },
      { "id": 2, "product_id": 0, "discount": 0, "amount": "10.0", "text": "", "product_code": null, "product_name": "My product 2", "product_unit": "", "product_price": "100.0", "product_tax": 12, "text_row": false, "sort_order": 1, "tax_deductible": false },
      { "id": 3, "product_id": 0, "discount": 0, "amount": "0.0",  "text": "Some arbitrary text", "product_code": null, "product_name": "", "product_unit": "", "product_price": "0.0", "product_tax": 0, "text_row": true, "sort_order": 2, "tax_deductible": false }
    ]
  }
}
```

**Example — create invoice for a new client**

```http
POST /api/v2/invoices
```

```json
{
  "date": "2021-01-25",
  "client": {
    "company": "Google",
    "address": {
      "street_address": "1600 Amphitheatre Parkway",
      "zip_code": "94043",
      "city": "Mountain View",
      "country": "SE"
    }
  },
  "rows": [
    { "product_name": "My product", "product_tax": 25, "product_price": "100", "amount": "10" }
  ]
}
```

Response: `201 Created` with full invoice data including the newly created `client_id`.

**Example — invalid invoice**

```http
POST /api/v2/invoices
```

```json
{
  "client_id": 0,
  "date": "",
  "rows": [
    { "product_code": "ABCD-ABCD-ABCD-ABCDABCD-ABCD-ABCD-" }
  ]
}
```

```json
422
{
  "errors": {
    "client_id": [{ "error": "blank" }],
    "rows": [
      {
        "0": {
          "rows.product_code": [
            { "error": "too_long", "count": 30 }
          ]
        }
      }
    ]
  }
}
```

---

#### `PUT /api/v2/invoices/:id` — Update an invoice

Accepts the same parameters as **Create an invoice**, with the exception of `client` (you cannot update a client through an invoice update).

**Example**

```http
PUT /api/v2/invoices/11
```

```json
{
  "date": "2021-01-26",
  "rows": [
    { "id": 14, "product_name": "Updated name" }
  ]
}
```

```
204
```

---

#### `POST /api/v2/invoices/:id/send` — Send an invoice

**Params**

| Name | Description |
| --- | --- |
| `delivery_method` | Must be one of: `email`, `letter`, `auto`. Optional, defaults to `auto` (which takes the delivery method from the client settings) |

**Example — error**

```http
POST /api/v2/invoices/8/send
```

```json
422
{ "error": "You must select at least one recipient." }
```

---

### Payments

#### `GET /api/v2/invoices/:invoice_id/payments` — List payments

**Example**

```http
GET /api/v2/invoices/5/payments
```

```json
200
{
  "data": [
    { "id": 2, "paid_at": "2021-01-25", "amount": "100.0", "invoice_id": 5 },
    { "id": 3, "paid_at": "2021-01-25", "amount": "200.0", "invoice_id": 5 }
  ],
  "paging": {
    "total_pages": 1,
    "current_page": 1,
    "next": null,
    "previous": null
  }
}
```

---

#### `POST /api/v2/invoices/:invoice_id/payments` — Add payment

**Params**

| Name | Description |
| --- | --- |
| `paid_at` | What date was the payment made? |

**Example**

```http
POST /api/v2/invoices/4/payments
```

```json
{ "paid_at": "2021-01-25" }
```

```json
201
{
  "data": {
    "id": 1,
    "paid_at": "2021-01-25",
    "amount": "1250.0",
    "invoice_id": 4
  }
}
```

---

## Libraries

### Official client libraries

There are official libraries you can use to easily connect your app/service to fakturan.nu. Each library comes with its own documentation and examples.

- **Fakturan.nu gem** (Ruby)
- **Fakturan.nu PHP client**

---

## CURL Examples — Sandbox

> Base URL: `https://sandbox.fakturan.nu`
>
> Use this environment for testing. The `--user` argument engages HTTP Basic Auth.

**Get a list of your products**

```bash
curl --user <your-api-key-id>:<your-api-key-password> \
  -H "Content-Type: application/json" \
  https://sandbox.fakturan.nu/api/v2/products
```

**Create a product**

```bash
curl --user <your-api-key-id>:<your-api-key-password> \
  -H "Content-Type: application/json" \
  -d '{"name": "Blue Suede Shoes", "unit": "pairs"}' \
  https://sandbox.fakturan.nu/api/v2/products
```

**Create an invoice**

```bash
curl --user <your-api-key-id>:<your-api-key-password> \
  -H "Content-Type: application/json" \
  -d '{"date": "20230101", "client": {"company": "Acme Shoe factory"}, "rows": [{"product_name": "Blue Suede Shoes", "unit": "pairs"}]}' \
  https://sandbox.fakturan.nu/api/v2/invoices
```

**Create an invoice and send it via email**

First, create the invoice. Don't forget to set the `email` field on the client:

```bash
curl --user <your-api-key-id>:<your-api-key-password> \
  -H "Content-Type: application/json" \
  -d '{"date": "20230101", "client": {"company": "Acme Shoe factory", "email": "test@mydomain.com"}, "rows": [{"product_name": "Blue Suede Shoes", "unit": "pairs"}]}' \
  https://sandbox.fakturan.nu/api/v2/invoices
```

Then grab the `id` from the response (`123` in this case):

```
# => Response: {"data":{"id":123,"number":1,"date":"2023-01-01","client_id":324,"days":30,"our_reference":"","your_reference":"","sent":false,"paid_at":null,"locale":"sv","currency":"SEK" ...
```

Issue a `POST` request to the **send** endpoint using the id from the response. A `delivery_method` param is optional.

```bash
curl --user <your-api-key-id>:<your-api-key-password> \
  -H "Content-Type: application/json" \
  -d {} \
  https://sandbox.fakturan.nu/api/v2/invoices/123/send
```

**Send a reminder**

Issue a `POST` request to the **send** endpoint using the `as_reminder` parameter:

```bash
curl --user <your-api-key-id>:<your-api-key-password> \
  -H "Content-Type: application/json" \
  -d '{"as_reminder": true}' \
  https://sandbox.fakturan.nu/api/v2/invoices/123/send
```

---

## CURL Examples — Production

> Base URL: `https://www.fakturan.nu`
>
> ⚠️ **This is the live environment — all actions affect real data, real clients, and real invoices.** Make sure you have tested everything in sandbox first.

**Get a list of your products**

```bash
curl --user <your-api-key-id>:<your-api-key-password> \
  -H "Content-Type: application/json" \
  https://www.fakturan.nu/api/v2/products
```

**Create a product**

```bash
curl --user <your-api-key-id>:<your-api-key-password> \
  -H "Content-Type: application/json" \
  -d '{"name": "Blue Suede Shoes", "unit": "pairs"}' \
  https://www.fakturan.nu/api/v2/products
```

**Create an invoice**

```bash
curl --user <your-api-key-id>:<your-api-key-password> \
  -H "Content-Type: application/json" \
  -d '{"date": "20230101", "client": {"company": "Acme Shoe factory"}, "rows": [{"product_name": "Blue Suede Shoes", "unit": "pairs"}]}' \
  https://www.fakturan.nu/api/v2/invoices
```

**Create an invoice and send it via email**

First, create the invoice. Don't forget to set the `email` field on the client:

```bash
curl --user <your-api-key-id>:<your-api-key-password> \
  -H "Content-Type: application/json" \
  -d '{"date": "20230101", "client": {"company": "Acme Shoe factory", "email": "test@mydomain.com"}, "rows": [{"product_name": "Blue Suede Shoes", "unit": "pairs"}]}' \
  https://www.fakturan.nu/api/v2/invoices
```

Then grab the `id` from the response (`123` in this case):

```
# => Response: {"data":{"id":123,"number":1,"date":"2023-01-01","client_id":324,"days":30,"our_reference":"","your_reference":"","sent":false,"paid_at":null,"locale":"sv","currency":"SEK" ...
```

Issue a `POST` request to the **send** endpoint using the id from the response. A `delivery_method` param is optional.

```bash
curl --user <your-api-key-id>:<your-api-key-password> \
  -H "Content-Type: application/json" \
  -d {} \
  https://www.fakturan.nu/api/v2/invoices/123/send
```

**Send a reminder**

Issue a `POST` request to the **send** endpoint using the `as_reminder` parameter:

```bash
curl --user <your-api-key-id>:<your-api-key-password> \
  -H "Content-Type: application/json" \
  -d '{"as_reminder": true}' \
  https://www.fakturan.nu/api/v2/invoices/123/send
```
