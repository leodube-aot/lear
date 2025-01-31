# Copyright © 2019 Province of British Columbia
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Tests to assure the business-filing end-point.

Test-Suite to ensure that the /businesses endpoint is working as expected.
"""
import asyncio
import copy
import json
from datetime import datetime
from http import HTTPStatus

import datedelta
import dpath.util
import pytest
from registry_schemas.example_data import (
    ANNUAL_REPORT,
    CHANGE_OF_ADDRESS,
    CORRECTION_AR,
    CORRECTION_INCORPORATION,
    FILING_HEADER,
    INCORPORATION_FILING_TEMPLATE,
)

from legal_api.models import Business, Filing
from legal_api.services import QueueService
from legal_api.services.authz import COLIN_SVC_ROLE, STAFF_ROLE
from tests import integration_nats, integration_payment
from tests.unit.services.utils import create_header
from tests.unit.models import factory_business_mailing_address, factory_business, factory_completed_filing, factory_filing, factory_epoch_filing  # noqa:E501,I001


def test_post_pre_load_colin_filing(session, client, jwt):
    """Assert that colin filing can be posted to legal api."""
    # SETUP
    # Create business
    identifier = 'CP7654321'
    business = factory_business(identifier, founding_date=(datetime.utcnow() - datedelta.YEAR))
    factory_business_mailing_address(business)
    # Create Epoch filing to be ahead of AR filing
    factory_epoch_filing(business, datetime.utcnow() + datedelta.DAY)
    # Create an AR filing for the business
    ar = copy.deepcopy(ANNUAL_REPORT)
    ar['filing']['annualReport']['annualReportDate'] = datetime.utcnow().date().isoformat()
    ar['filing']['annualReport']['annualGeneralMeetingDate'] = datetime.utcnow().date().isoformat()
    ar['filing']['header']['colinIds'] = [1230]
    ar['filing']['header']['date'] = datetime.utcnow().date().isoformat()
    ar['filing']['header']['source'] = Filing.Source.COLIN.value
    ar['filing']['business']['identifier'] = identifier

    # POST the AR
    rv = client.post(
        f'/api/v1/businesses/{identifier}/filings',
        json=ar,
        headers=create_header(jwt, [COLIN_SVC_ROLE], 'coops-updater-job')
    )
    # Assure that the filing was accepted
    assert rv.status_code == HTTPStatus.CREATED

    # Check filing
    filing = Filing.find_by_id(rv.json['filing']['id'])
    assert filing.source == Filing.Source.COLIN.value
    assert filing.status == Filing.Status.COMPLETED.value


@integration_nats
@pytest.mark.asyncio
def test_post_colin_filing(session, client, jwt):
    """Assert that colin filing can be posted to legal api."""
    # SETUP
    # Create business
    identifier = 'CP7654321'
    business = factory_business(identifier, founding_date=(datetime.utcnow() - datedelta.YEAR))
    factory_business_mailing_address(business)

    # Create an AR filing for the business
    ar = copy.deepcopy(ANNUAL_REPORT)
    ar['filing']['annualReport']['annualReportDate'] = datetime.utcnow().date().isoformat()
    ar['filing']['annualReport']['annualGeneralMeetingDate'] = datetime.utcnow().date().isoformat()
    ar['filing']['header']['colinIds'] = [1230]
    ar['filing']['header']['date'] = datetime.utcnow().date().isoformat()
    ar['filing']['header']['source'] = Filing.Source.COLIN.value
    ar['filing']['business']['identifier'] = identifier

    # POST the AR
    rv = client.post(
        f'/api/v1/businesses/{identifier}/filings',
        json=ar,
        headers=create_header(jwt, [COLIN_SVC_ROLE], 'coops-updater-job')
    )
    # Assure that the filing was accepted
    assert rv.status_code == HTTPStatus.CREATED

    # Check filing
    filing = Filing.find_by_id(rv.json['filing']['id'])
    assert filing.source == Filing.Source.COLIN.value
    assert filing.status in [Filing.Status.PAID.value, Filing.Status.COMPLETED.value]


@integration_nats
@pytest.mark.asyncio
async def test_colin_filing_failed_to_queue(app_ctx, session, client, jwt, stan_server, event_loop):
    """Assert that payment tokens can be retrieved and decoded from the Queue."""
    # SETUP
    this_loop = asyncio.get_event_loop()
    this_loop = event_loop
    queue = QueueService(app_ctx, this_loop)
    await queue.connect()

    # TEST - add some COLIN filings to the system, check that they got placed on the Queue
    # Create business
    identifier = 'CP7654321'
    business = factory_business(identifier,
                                founding_date=(datetime.utcnow() - datedelta.YEAR)
                                )
    factory_epoch_filing(business)
    factory_business_mailing_address(business)
    ar = copy.deepcopy(ANNUAL_REPORT)
    ar['filing']['annualReport']['annualReportDate'] = datetime.utcnow().date().isoformat()
    ar['filing']['annualReport']['annualGeneralMeetingDate'] = datetime.utcnow().date().isoformat()
    ar['filing']['header']['date'] = datetime.utcnow().date().isoformat()

    # POST the AR
    rv = client.post(f'/api/v1/businesses/{identifier}/filings',
                     json=ar,
                     headers=create_header(jwt, [COLIN_SVC_ROLE], 'coops-updater-job')
                     )

    # Assure that the filing was rejected
    assert rv.status_code == HTTPStatus.BAD_REQUEST
    assert 'missing filing/header values' in rv.json['errors'][0]['message']


@integration_nats
# @pytest.mark.asyncio
def test_colin_filing_to_queue(app_ctx, session, client, jwt, stan_server):
    """Assert that colin filing is added to the queue."""
    # SETUP
    msgs = []
    filing_ids = []
    this_loop = asyncio.get_event_loop()
    # this_loop = event_loop
    future = asyncio.Future(loop=this_loop)
    queue = QueueService(app_ctx, this_loop)
    this_loop.run_until_complete(queue.connect())

    async def cb(msg):
        nonlocal msgs
        nonlocal future
        msgs.append(msg)
        if len(msgs) == 5:
            future.set_result(True)

    this_loop.run_until_complete(queue.stan.subscribe(subject=queue.subject,
                                                      queue='colin_queue',
                                                      durable_name='colin_queue',
                                                      cb=cb))

    # TEST - add some COLIN filings to the system, check that they got placed on the Queue
    for i in range(0, 5):
        # Create business
        identifier = f'CP765432{i}'
        business = factory_business(identifier,
                                    founding_date=(datetime.utcnow() - datedelta.YEAR)
                                    )
        factory_business_mailing_address(business)
        # Create anm AR filing for the business
        ar = copy.deepcopy(ANNUAL_REPORT)
        ar['filing']['annualReport']['annualReportDate'] = datetime.utcnow().date().isoformat()
        ar['filing']['annualReport']['annualGeneralMeetingDate'] = datetime.utcnow().date().isoformat()
        ar['filing']['header']['colinIds'] = [1230 + i]
        ar['filing']['header']['date'] = datetime.utcnow().date().isoformat()
        ar['filing']['business']['identifier'] = identifier

        # POST the AR
        rv = client.post(f'/api/v1/businesses/{identifier}/filings',
                         json=ar,
                         headers=create_header(jwt, [COLIN_SVC_ROLE], 'coops-updater-job')
                         )

        # Assure that the filing was accepted
        assert rv.status_code == HTTPStatus.CREATED

        filing_ids.append(rv.json['filing']['id'])

    # Await all the messages were received
    try:
        this_loop.run_until_complete(asyncio.wait_for(future, 2, loop=this_loop))
    except Exception as err:
        print(err)

    # CHECK the colinFilings were retrieved from the queue
    assert len(msgs) == 5
    for i in range(0, 5):
        m = msgs[i]
        assert 'filing' in m.data.decode('utf-8')
        assert dpath.util.get(json.loads(m.data.decode('utf-8')), 'filing/id') in filing_ids


@integration_payment
def test_update_ar_with_colin_id_set(session, client, jwt):
    """Assert that when a filing with colinId set (as when colin updates legal api) that colin_event_id is set."""
    identifier = 'CP7654321'
    business = factory_business(identifier, founding_date=(datetime.utcnow() - datedelta.YEAR))
    factory_business_mailing_address(business)
    ar = copy.deepcopy(ANNUAL_REPORT)
    ar['filing']['annualReport']['annualReportDate'] = datetime.utcnow().date().isoformat()
    ar['filing']['annualReport']['annualGeneralMeetingDate'] = datetime.utcnow().date().isoformat()
    ar['filing']['header']['date'] = datetime.utcnow().date().isoformat()

    filing = factory_filing(business, ar)

    ar['filing']['header']['colinIds'] = [1234]

    rv = client.put(
        f'/api/v1/businesses/{identifier}/filings/{filing.id}',
        json=ar,
        headers=create_header(jwt, [STAFF_ROLE], identifier)
    )

    assert rv.status_code == HTTPStatus.ACCEPTED
    assert rv.json['filing']['business'] == ar['filing']['business']
    assert rv.json['filing']['annualReport'] == ar['filing']['annualReport']
    assert not rv.json['filing']['header'].get('colinIds')
    assert rv.json['filing']['header']['filingId'] == filing.id


def test_get_internal_filings(session, client, jwt):
    """Assert that the internal filings get endpoint returns all completed filings without colin ids."""
    from legal_api.models.colin_event_id import ColinEventId
    from tests.unit.models import factory_error_filing, factory_pending_filing
    # setup
    identifier = 'CP7654321'
    b = factory_business(identifier)
    factory_business_mailing_address(b)

    filing1 = factory_completed_filing(b, ANNUAL_REPORT)
    filing2 = factory_completed_filing(b, ANNUAL_REPORT)
    filing3 = factory_pending_filing(b, ANNUAL_REPORT)
    filing4 = factory_filing(b, ANNUAL_REPORT)
    filing5 = factory_error_filing(b, ANNUAL_REPORT)
    filing6 = factory_completed_filing(b, CORRECTION_AR)

    assert filing1.status == Filing.Status.COMPLETED.value
    # completed with colin_event_id
    print(filing2.colin_event_ids)
    assert len(filing2.colin_event_ids) == 0
    colin_event_id = ColinEventId()
    colin_event_id.colin_event_id = 12345
    filing2.colin_event_ids.append(colin_event_id)
    filing2.save()
    assert filing2.status == Filing.Status.COMPLETED.value
    assert filing2.colin_event_ids
    # pending with no colin_event_ids
    assert filing3.status == Filing.Status.PENDING.value
    # draft with no colin_event_ids
    assert filing4.status == Filing.Status.DRAFT.value
    # error with no colin_event_ids
    assert filing5.status == Filing.Status.PAID.value
    # completed correction with no colin_event_ids
    assert filing6.status == Filing.Status.COMPLETED.value

    # test endpoint returned filing1 only (completed, no corrections, with no colin id set)
    rv = client.get('/api/v1/businesses/internal/filings')
    assert rv.status_code == HTTPStatus.OK
    assert len(rv.json) == 1
    assert rv.json[0]['filingId'] == filing1.id


def test_patch_internal_filings(session, client, jwt):
    """Assert that the internal filings patch endpoint updates the colin_event_id."""
    from legal_api.models.colin_event_id import ColinEventId
    # setup
    identifier = 'CP7654321'
    b = factory_business(identifier)
    factory_business_mailing_address(b)
    filing = factory_completed_filing(b, ANNUAL_REPORT)
    colin_id = 1234

    # make request
    rv = client.patch(f'/api/v1/businesses/internal/filings/{filing.id}',
                      json={'colinIds': [colin_id]},
                      headers=create_header(jwt, [COLIN_SVC_ROLE])
                      )

    # test result
    assert rv.status_code == HTTPStatus.ACCEPTED
    filing = Filing.find_by_id(filing.id)
    assert colin_id in ColinEventId.get_by_filing_id(filing.id)
    assert rv.json['filing']['header']['filingId'] == filing.id
    assert colin_id in rv.json['filing']['header']['colinIds']


def test_get_colin_id(session, client, jwt):
    """Assert the internal/filings/colin_id get endpoint returns properly."""
    from legal_api.models.colin_event_id import ColinEventId
    # setup
    identifier = 'CP7654321'
    b = factory_business(identifier)
    factory_business_mailing_address(b)
    filing = factory_completed_filing(b, ANNUAL_REPORT)
    colin_event_id = ColinEventId()
    colin_event_id.colin_event_id = 1234
    filing.colin_event_ids.append(colin_event_id)
    filing.save()

    rv = client.get(f'/api/v1/businesses/internal/filings/colin_id/{colin_event_id.colin_event_id}')
    assert rv.status_code == HTTPStatus.OK
    assert rv.json == {'colinId': colin_event_id.colin_event_id}

    rv = client.get(f'/api/v1/businesses/internal/filings/colin_id/{1}')
    assert rv.status_code == HTTPStatus.NOT_FOUND


def test_get_colin_last_update(session, client, jwt):
    """Assert the get endpoint for ColinLastUpdate returns last updated colin id."""
    from tests.unit.models import db
    # setup
    colin_id = 1234
    db.session.execute(
        f"""
        insert into colin_last_update (last_update, last_event_id)
        values (current_timestamp, {colin_id})
        """
    )

    rv = client.get('/api/v1/businesses/internal/filings/colin_id')
    assert rv.status_code == HTTPStatus.OK
    assert rv.json == {'maxId': colin_id}


def test_post_colin_last_update(session, client, jwt):
    """Assert the internal/filings/colin_id post endpoint updates the colin_last_update table."""
    colin_id = 1234
    rv = client.post(f'/api/v1/businesses/internal/filings/colin_id/{colin_id}',
                     headers=create_header(jwt, [COLIN_SVC_ROLE])
                     )
    assert rv.status_code == HTTPStatus.CREATED
    assert rv.json == {'maxId': colin_id}


def test_future_filing_coa(session, client, jwt):
    """Assert that future effective filings are saved and have the correct status changes."""
    import pytz
    from tests.unit.models import factory_pending_filing
    # setup
    identifier = 'CP7654321'
    b = factory_business(identifier, (datetime.utcnow() - datedelta.YEAR), None, Business.LegalTypes.BCOMP.value)
    factory_business_mailing_address(b)
    coa = copy.deepcopy(FILING_HEADER)
    coa['filing']['header']['name'] = 'changeOfAddress'
    coa['filing']['changeOfAddress'] = CHANGE_OF_ADDRESS
    coa['filing']['changeOfAddress']['offices']['registeredOffice']['deliveryAddress']['addressCountry'] = 'CA'
    coa['filing']['changeOfAddress']['offices']['registeredOffice']['mailingAddress']['addressCountry'] = 'CA'
    coa['filing']['business']['identifier'] = identifier

    filing = factory_pending_filing(b, coa)
    filing.effective_date = datetime.utcnow() + datedelta.DAY
    filing.save()
    assert filing.status == Filing.Status.PENDING.value

    filing.payment_completion_date = pytz.utc.localize(datetime.utcnow())
    filing.save()

    assert filing.status == Filing.Status.PAID.value

    rv = client.get('/api/v1/businesses/internal/filings/PAID', headers=create_header(jwt, [COLIN_SVC_ROLE]))
    paid_filings = rv.json
    assert paid_filings[0]
    # check values that future effective filings job depends on are there
    assert paid_filings[0]['filing']['header']['filingId'] == filing.id
    assert paid_filings[0]['filing']['header']['paymentToken']
    assert paid_filings[0]['filing']['header']['effectiveDate']
